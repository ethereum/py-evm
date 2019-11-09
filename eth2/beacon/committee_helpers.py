import logging
from typing import Iterable, Sequence, Tuple

from eth_typing import Hash32
from eth_utils import ValidationError, to_tuple

from eth2._utils.hash import hash_eth2
from eth2.beacon.constants import MAX_INDEX_COUNT, MAX_RANDOM_BYTE
from eth2.beacon.helpers import (
    compute_epoch_at_slot,
    compute_start_slot_at_epoch,
    get_active_validator_indices,
    get_seed,
    signature_domain_to_domain_type,
)
from eth2.beacon.signature_domain import SignatureDomain
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.validators import Validator
from eth2.beacon.typing import CommitteeIndex, Epoch, Gwei, Slot, ValidatorIndex
from eth2.configs import CommitteeConfig

logger = logging.getLogger("eth2.beacon.committee_helpers")


def get_committee_count_at_slot(
    state: BeaconState,
    slot: Slot,
    max_committees_per_slot: int,
    slots_per_epoch: int,
    target_committee_size: int,
) -> int:
    epoch = compute_epoch_at_slot(slot, slots_per_epoch)
    return get_committee_count_per_slot_at_epoch(
        state, epoch, max_committees_per_slot, slots_per_epoch, target_committee_size
    )


def get_committee_count_per_slot_at_epoch(
    state: BeaconState,
    epoch: Epoch,
    max_committees_per_slot: int,
    slots_per_epoch: int,
    target_committee_size: int,
) -> int:
    active_validator_indices = get_active_validator_indices(state.validators, epoch)
    return max(
        1,
        min(
            max_committees_per_slot,
            len(active_validator_indices) // slots_per_epoch // target_committee_size,
        ),
    )


def compute_proposer_index(
    validators: Sequence[Validator],
    indices: Sequence[ValidatorIndex],
    seed: Hash32,
    max_effective_balance: Gwei,
    shuffle_round_count: int,
) -> ValidatorIndex:
    """
    Return from ``indices`` a random index sampled by effective balance.
    """
    if len(indices) == 0:
        raise ValidationError("There is no any active validator.")

    i = 0
    while True:
        candidate_index = indices[
            compute_shuffled_index(
                ValidatorIndex(i % len(indices)),
                len(indices),
                seed,
                shuffle_round_count,
            )
        ]
        random_byte = hash_eth2(seed + (i // 32).to_bytes(8, "little"))[i % 32]
        effective_balance = validators[candidate_index].effective_balance
        if effective_balance * MAX_RANDOM_BYTE >= max_effective_balance * random_byte:
            return ValidatorIndex(candidate_index)

        # Log the warning message in case it happends.
        if i % len(indices) == 0 and i > 0:
            logger.warning(
                "Tried over %d times in compute_proposer_index while loop.", i
            )

        i += 1


def get_beacon_proposer_index(
    state: BeaconState, committee_config: CommitteeConfig
) -> ValidatorIndex:
    """
    Return the current beacon proposer index.
    """
    current_epoch = state.current_epoch(committee_config.SLOTS_PER_EPOCH)
    domain_type = signature_domain_to_domain_type(
        SignatureDomain.DOMAIN_BEACON_PROPOSER
    )

    seed = hash_eth2(
        get_seed(state, current_epoch, domain_type, committee_config)
        + state.slot.to_bytes(8, "little")
    )
    indices = get_active_validator_indices(state.validators, current_epoch)
    return compute_proposer_index(
        state.validators,
        indices,
        seed,
        committee_config.MAX_EFFECTIVE_BALANCE,
        committee_config.SHUFFLE_ROUND_COUNT,
    )


def compute_shuffled_index(
    index: int, index_count: int, seed: Hash32, shuffle_round_count: int
) -> int:
    """
    Return `p(index)` in a pseudorandom permutation `p` of `0...index_count-1`
    with ``seed`` as entropy.

    Utilizes 'swap or not' shuffling found in
    https://link.springer.com/content/pdf/10.1007%2F978-3-642-32009-5_1.pdf
    See the 'generalized domain' algorithm on page 3.
    """
    if index >= index_count:
        raise ValidationError(
            f"The given `index` ({index}) should be less than `index_count` ({index_count}"
        )

    if index_count > MAX_INDEX_COUNT:
        raise ValidationError(
            f"The given `index_count` ({index_count}) should be equal to or less than "
            f"`MAX_INDEX_COUNT` ({MAX_INDEX_COUNT}"
        )

    new_index = index
    for current_round in range(shuffle_round_count):
        pivot = (
            int.from_bytes(
                hash_eth2(seed + current_round.to_bytes(1, "little"))[0:8], "little"
            )
            % index_count
        )

        flip = (pivot + index_count - new_index) % index_count
        position = max(new_index, flip)
        source = hash_eth2(
            seed
            + current_round.to_bytes(1, "little")
            + (position // 256).to_bytes(4, "little")
        )
        byte = source[(position % 256) // 8]
        bit = (byte >> (position % 8)) % 2
        new_index = flip if bit else new_index

    return new_index


@to_tuple
def _compute_committee(
    indices: Sequence[ValidatorIndex],
    seed: Hash32,
    index: int,
    count: int,
    shuffle_round_count: int,
) -> Iterable[ValidatorIndex]:
    start = (len(indices) * index) // count
    end = (len(indices) * (index + 1)) // count
    for i in range(start, end):
        shuffled_index = compute_shuffled_index(
            i, len(indices), seed, shuffle_round_count
        )
        yield indices[shuffled_index]


def get_beacon_committee(
    state: BeaconState, slot: Slot, index: CommitteeIndex, config: CommitteeConfig
) -> Tuple[ValidatorIndex, ...]:
    epoch = compute_epoch_at_slot(slot, config.SLOTS_PER_EPOCH)
    committees_per_slot = get_committee_count_at_slot(
        state,
        slot,
        config.MAX_COMMITTEES_PER_SLOT,
        config.SLOTS_PER_EPOCH,
        config.TARGET_COMMITTEE_SIZE,
    )

    active_validator_indices = get_active_validator_indices(state.validators, epoch)

    domain_type = signature_domain_to_domain_type(
        SignatureDomain.DOMAIN_BEACON_ATTESTER
    )

    return _compute_committee(
        indices=active_validator_indices,
        seed=get_seed(state, epoch, domain_type, config),
        index=(slot % config.SLOTS_PER_EPOCH) * committees_per_slot + index,
        count=committees_per_slot * config.SLOTS_PER_EPOCH,
        shuffle_round_count=config.SHUFFLE_ROUND_COUNT,
    )


def iterate_committees_at_epoch(
    state: BeaconState, epoch: Epoch, config: CommitteeConfig
) -> Iterable[Tuple[Tuple[ValidatorIndex, ...], CommitteeIndex, Slot]]:
    """
    Iterate ``committee``, ``committee_index``, ``slot`` of the given ``epoch``.
    """
    epoch_start_slot = compute_start_slot_at_epoch(epoch, config.SLOTS_PER_EPOCH)
    committees_per_slot = get_committee_count_per_slot_at_epoch(
        state,
        epoch,
        config.MAX_COMMITTEES_PER_SLOT,
        config.SLOTS_PER_EPOCH,
        config.TARGET_COMMITTEE_SIZE,
    )
    for slot in range(epoch_start_slot, epoch_start_slot + config.SLOTS_PER_EPOCH):
        yield from iterate_committees_at_slot(
            state, Slot(slot), committees_per_slot, config
        )


def iterate_committees_at_slot(
    state: BeaconState, slot: Slot, committees_per_slot: int, config: CommitteeConfig
) -> Iterable[Tuple[Tuple[ValidatorIndex, ...], CommitteeIndex, Slot]]:
    """
    Iterate ``committee``, ``committee_index``, ``slot`` of the given ``slot``.
    """
    for committee_index in range(committees_per_slot):
        committee = get_beacon_committee(
            state, slot, CommitteeIndex(committee_index), config
        )
        yield committee, CommitteeIndex(committee_index), slot
