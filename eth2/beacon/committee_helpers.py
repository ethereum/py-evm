from typing import (
    Iterable,
    Sequence,
)

from eth_utils import (
    to_tuple,
    ValidationError,
)
from eth_typing import (
    Hash32,
)

from eth2._utils.hash import (
    hash_eth2,
)
from eth2.configs import (
    CommitteeConfig,
)
from eth2.beacon.constants import (
    MAX_RANDOM_BYTE,
    MAX_INDEX_COUNT,
)
from eth2.beacon.helpers import (
    generate_seed,
    get_active_validator_indices,
)
from eth2.beacon.typing import (
    Epoch,
    Shard,
    ValidatorIndex,
)
from eth2.beacon.types.states import BeaconState


def get_epoch_committee_count(active_validator_count: int,
                              shard_count: int,
                              slots_per_epoch: int,
                              target_committee_size: int) -> int:
    return max(
        1,
        min(
            shard_count // slots_per_epoch,
            active_validator_count // slots_per_epoch // target_committee_size,
        )
    ) * slots_per_epoch


def get_shard_delta(state: BeaconState,
                    epoch: Epoch,
                    config: CommitteeConfig) -> int:
    shard_count = config.SHARD_COUNT
    slots_per_epoch = config.SLOTS_PER_EPOCH

    active_validator_indices = get_active_validator_indices(state.validators, epoch)

    return min(
        get_epoch_committee_count(
            len(active_validator_indices),
            shard_count,
            slots_per_epoch,
            config.TARGET_COMMITTEE_SIZE,
        ),
        shard_count - shard_count // slots_per_epoch,
    )


def get_epoch_start_shard(state: BeaconState,
                          epoch: Epoch,
                          config: CommitteeConfig) -> Shard:
    current_epoch = state.current_epoch(config.SLOTS_PER_EPOCH)
    next_epoch = state.next_epoch(config.SLOTS_PER_EPOCH)
    if epoch > next_epoch:
        raise ValidationError("Asking for start shard for an epoch after next")

    check_epoch = int(next_epoch)
    shard = (
        state.start_shard + get_shard_delta(state, current_epoch, config)
    ) % config.SHARD_COUNT
    while check_epoch > epoch:
        check_epoch -= 1
        shard = (
            shard + config.SHARD_COUNT - get_shard_delta(state, Epoch(check_epoch), config)
        ) % config.SHARD_COUNT
    return shard


def get_beacon_proposer_index(state: BeaconState,
                              committee_config: CommitteeConfig) -> ValidatorIndex:
    """
    Return the current beacon proposer index.
    """
    slots_per_epoch = committee_config.SLOTS_PER_EPOCH
    shard_count = committee_config.SHARD_COUNT
    target_committee_size = committee_config.TARGET_COMMITTEE_SIZE
    max_effective_balance = committee_config.MAX_EFFECTIVE_BALANCE

    current_slot = state.slot
    current_epoch = state.current_epoch(slots_per_epoch)
    active_validator_indices = get_active_validator_indices(state.validators, current_epoch)
    committees_per_slot = get_epoch_committee_count(
        len(active_validator_indices),
        shard_count,
        slots_per_epoch,
        target_committee_size,
    ) // slots_per_epoch
    offset = committees_per_slot * (current_slot % slots_per_epoch)
    shard = (
        get_epoch_start_shard(state, current_epoch, committee_config) + offset
    ) % shard_count
    first_committee = get_crosslink_committee(
        state,
        current_epoch,
        shard,
        committee_config,
    )
    seed = generate_seed(state, current_epoch, committee_config)
    i = 0
    first_committee_len = len(first_committee)
    while True:
        candidate_index = first_committee[(current_epoch + i) % first_committee_len]
        random_byte = hash_eth2(seed + (i // 32).to_bytes(8, "little"))[i % 32]
        effective_balance = state.validators[candidate_index].effective_balance
        if effective_balance * MAX_RANDOM_BYTE >= max_effective_balance * random_byte:
            return candidate_index
        i += 1


def _get_shuffled_index(index: int,
                        index_count: int,
                        seed: Hash32,
                        shuffle_round_count: int) -> int:
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
        pivot = int.from_bytes(
            hash_eth2(seed + current_round.to_bytes(1, 'little'))[0:8],
            'little',
        ) % index_count

        flip = (pivot + index_count - new_index) % index_count
        hash_pos = max(new_index, flip)
        h = hash_eth2(
            seed +
            current_round.to_bytes(1, 'little') +
            (hash_pos // 256).to_bytes(4, 'little')
        )
        byte = h[(hash_pos % 256) // 8]
        bit = (byte >> (hash_pos % 8)) % 2
        new_index = flip if bit else new_index

    return new_index


def _compute_committee(indices: Sequence[ValidatorIndex],
                       seed: Hash32,
                       index: int,
                       count: int,
                       shuffle_round_count: int) -> Iterable[ValidatorIndex]:
    start = (len(indices) * index) // count
    end = (len(indices) * (index + 1)) // count
    for i in range(start, end):
        shuffled_index = _get_shuffled_index(i, len(indices), seed, shuffle_round_count)
        yield indices[shuffled_index]


@to_tuple
def get_crosslink_committee(state: BeaconState,
                            epoch: Epoch,
                            shard: Shard,
                            config: CommitteeConfig) -> Iterable[ValidatorIndex]:
    target_shard = (
        shard + config.SHARD_COUNT - get_epoch_start_shard(state, epoch, config)
    ) % config.SHARD_COUNT

    active_validator_indices = get_active_validator_indices(
        state.validators,
        epoch,
    )

    return _compute_committee(
        indices=active_validator_indices,
        seed=generate_seed(state, epoch, config),
        index=target_shard,
        count=get_epoch_committee_count(
            len(active_validator_indices),
            config.SHARD_COUNT,
            config.SLOTS_PER_EPOCH,
            config.TARGET_COMMITTEE_SIZE,
        ),
        shuffle_round_count=config.SHUFFLE_ROUND_COUNT,
    )
