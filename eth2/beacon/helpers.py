from typing import (
    Iterable,
    Sequence,
    Tuple,
    TYPE_CHECKING,
)

import functools

from eth_utils import (
    to_tuple,
    ValidationError,
)
from eth_typing import (
    Hash32,
)

from eth._utils.numeric import (
    clamp,
)

from eth2._utils.bitfield import (
    get_bitfield_length,
    has_voted,
)
import eth2._utils.bls as bls
from eth2._utils.numeric import (
    bitwise_xor,
)
from eth2.beacon._utils.random import (
    shuffle,
    split,
)
from eth2.beacon.constants import (
    GWEI_PER_ETH,
)
from eth2.beacon.enums import (
    SignatureDomain,
)
from eth2.beacon.typing import (
    Bitfield,
    BLSPubkey,
    Ether,
    Gwei,
    ShardNumber,
    SlotNumber,
    ValidatorIndex,
)
from eth2.beacon.validation import (
    validate_slot_for_state_slot,
)

if TYPE_CHECKING:
    from eth2.beacon.types.attestation_data import AttestationData  # noqa: F401
    from eth2.beacon.types.blocks import BaseBeaconBlock  # noqa: F401
    from eth2.beacon.types.states import BeaconState  # noqa: F401
    from eth2.beacon.types.fork_data import ForkData  # noqa: F401
    from eth2.beacon.types.slashable_vote_data import SlashableVoteData  # noqa: F401
    from eth2.beacon.types.validator_records import ValidatorRecord  # noqa: F401


#
# Get block root
#
def _get_block_root(
        latest_block_roots: Sequence[Hash32],
        state_slot: SlotNumber,
        slot: SlotNumber,
        latest_block_roots_length: int) -> Hash32:
    """
    Return the block root at a recent ``slot``.
    """
    if state_slot > slot + latest_block_roots_length:
        raise ValidationError(
            "state.slot ({}) should be less than or equal to "
            "(slot + latest_block_roots_length) ({}), "
            "where slot={}, latest_block_roots_length={}".format(
                state_slot,
                slot + latest_block_roots_length,
                slot,
                latest_block_roots_length,
            )
        )
    if slot >= state_slot:
        raise ValidationError(
            "slot ({}) should be less than state.slot ({})".format(
                slot,
                state_slot,
            )
        )
    return latest_block_roots[slot % latest_block_roots_length]


def get_block_root(
        state: 'BeaconState',
        slot: SlotNumber,
        latest_block_roots_length: int) -> Hash32:
    """
    Return the block root at a recent ``slot``.
    """
    return _get_block_root(
        state.latest_block_roots,
        state.slot,
        slot,
        latest_block_roots_length,
    )


def get_active_validator_indices(validators: Sequence['ValidatorRecord'],
                                 slot: SlotNumber) -> Tuple[ValidatorIndex, ...]:
    """
    Get indices of active validators from ``validators``.
    """
    return tuple(
        ValidatorIndex(index)for index, validator in enumerate(validators)
        if validator.is_active(slot)
    )


#
# Shuffling
#
def get_committee_count_per_slot(active_validator_count: int,
                                 shard_count: int,
                                 epoch_length: int,
                                 target_committee_size: int) -> int:
    return clamp(
        1,
        shard_count // epoch_length,
        active_validator_count // epoch_length // target_committee_size,
    )


def get_shuffling(*,
                  seed: Hash32,
                  validators: Sequence['ValidatorRecord'],
                  slot: SlotNumber,
                  epoch_length: int,
                  target_committee_size: int,
                  shard_count: int) -> Tuple[Iterable[ValidatorIndex], ...]:
    """
    Shuffle ``validators`` into crosslink committees seeded by ``seed`` and ``slot``.
    Return a list of ``EPOCH_LENGTH * committees_per_slot`` committees where each
    committee is itself a list of validator indices.

    If ``get_shuffling(seed, validators, slot)`` returns some value ``x``, it should return
    the same value ``x`` for the same seed and slot and possible future modifications of
    validators forever in phase 0, and until the ~1 year deletion delay in phase 2 and in the
    future.
    """
    # Normalizes slot to start of epoch boundary
    slot = SlotNumber(slot - slot % epoch_length)

    active_validator_indices = get_active_validator_indices(validators, slot)

    committees_per_slot = get_committee_count_per_slot(
        len(active_validator_indices),
        shard_count,
        epoch_length,
        target_committee_size,
    )

    # Shuffle
    seed = bitwise_xor(seed, Hash32(slot.to_bytes(32, byteorder="big")))
    shuffled_active_validator_indices = shuffle(active_validator_indices, seed)

    # Split the shuffled list into epoch_length * committees_per_slot pieces
    return tuple(
        split(
            shuffled_active_validator_indices,
            committees_per_slot * epoch_length,
        )
    )


def get_previous_epoch_committee_count_per_slot(state: 'BeaconState',
                                                shard_count: int,
                                                epoch_length: int,
                                                target_committee_size: int) -> int:
    previous_active_validators = get_active_validator_indices(
        state.validator_registry,
        state.previous_epoch_calculation_slot,
    )

    return get_committee_count_per_slot(
        active_validator_count=len(previous_active_validators),
        shard_count=shard_count,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
    )


def get_current_epoch_committee_count_per_slot(state: 'BeaconState',
                                               shard_count: int,
                                               epoch_length: int,
                                               target_committee_size: int) -> int:
    current_active_validators = get_active_validator_indices(
        state.validator_registry,
        state.current_epoch_calculation_slot,
    )
    return get_committee_count_per_slot(
        active_validator_count=len(current_active_validators),
        shard_count=shard_count,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
    )


@to_tuple
def get_crosslink_committees_at_slot(
        state: 'BeaconState',
        slot: SlotNumber,
        epoch_length: int,
        target_committee_size: int,
        shard_count: int) -> Iterable[Tuple[Iterable[ValidatorIndex], ShardNumber]]:
    """
    Return the list of ``(committee, shard)`` tuples for the ``slot``.
    """
    validate_slot_for_state_slot(
        state_slot=state.slot,
        slot=slot,
        epoch_length=epoch_length,
    )

    state_epoch_slot = state.slot - (state.slot % epoch_length)
    offset = slot % epoch_length

    if slot < state_epoch_slot:
        committees_per_slot = get_previous_epoch_committee_count_per_slot(
            state,
            shard_count=shard_count,
            epoch_length=epoch_length,
            target_committee_size=target_committee_size,
        )

        seed = state.previous_epoch_randao_mix
        shuffling_slot = state.previous_epoch_calculation_slot
        shuffling_start_shard = state.previous_epoch_start_shard
    else:
        committees_per_slot = get_current_epoch_committee_count_per_slot(
            state,
            shard_count=shard_count,
            epoch_length=epoch_length,
            target_committee_size=target_committee_size,
        )
        seed = state.current_epoch_randao_mix
        shuffling_slot = state.current_epoch_calculation_slot
        shuffling_start_shard = state.current_epoch_start_shard

    offset = slot % epoch_length
    shuffling = get_shuffling(
        seed=seed,
        validators=state.validator_registry,
        slot=shuffling_slot,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )
    slot_start_shard = (
        shuffling_start_shard +
        committees_per_slot * offset
    ) % shard_count

    for index in range(committees_per_slot):
        committee = shuffling[committees_per_slot * offset + index]
        yield (
            committee,
            ShardNumber((slot_start_shard + index) % shard_count),
        )


#
# Get proposer position
#

def get_beacon_proposer_index(state: 'BeaconState',
                              slot: SlotNumber,
                              epoch_length: int,
                              target_committee_size: int,
                              shard_count: int) -> ValidatorIndex:
    """
    Return the beacon proposer index for the ``slot``.
    """
    crosslink_committees_at_slot = get_crosslink_committees_at_slot(
        state=state,
        slot=slot,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )
    try:
        first_crosslink_committee = crosslink_committees_at_slot[0]
    except IndexError:
        raise ValidationError("crosslink_committees should not be empty.")

    first_committee, _ = first_crosslink_committee
    if len(first_committee) <= 0:
        raise ValidationError(
            "The first committee should not be empty"
        )

    return first_committee[slot % len(first_committee)]


def _get_committee_for_shard(
        crosslink_committees: Sequence[Tuple[Sequence[ValidatorIndex], ShardNumber]],
        shard: ShardNumber) -> Iterable[ValidatorIndex]:
    for committee, committee_shard in crosslink_committees:
        if committee_shard == shard:
            return committee
    return None


@to_tuple
def get_attestation_participants(state: 'BeaconState',
                                 attestation_data: 'AttestationData',
                                 aggregation_bitfield: Bitfield,
                                 epoch_length: int,
                                 target_committee_size: int,
                                 shard_count: int) -> Iterable[ValidatorIndex]:
    """
    Return the participant indices at for the ``attestation_data`` and ``aggregation_bitfield``.
    """
    # Find the committee in the list with the desired shard
    crosslink_committees = get_crosslink_committees_at_slot(
        state=state,
        slot=attestation_data.slot,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )

    if attestation_data.shard not in set([shard for _, shard in crosslink_committees]):
        raise ValidationError(
            "attestation_data.shard ({}) is not in crosslink_committees".format(
                attestation_data.shard,
            )
        )

    try:
        # Filter by shard
        committee = tuple(
            _get_committee_for_shard(crosslink_committees, attestation_data.shard)
        )
    except IndexError:
        raise ValidationError(
            "committee for shard={} should not be empty.".format(
                attestation_data.shard,
            )
        )

    committee_size = len(committee)
    if len(aggregation_bitfield) != get_bitfield_length(committee_size):
        raise ValidationError(
            'Invalid bitfield length,'
            "\texpected: {}, found: {}".format(
                get_bitfield_length(committee_size),
                len(attestation_data),
            )
        )

    # Find the participating attesters in the committee
    for bitfield_index, validator_index in enumerate(committee):
        if has_voted(aggregation_bitfield, bitfield_index):
            yield validator_index


#
# Misc
#
def get_effective_balance(
        validator_balances: Sequence[Gwei],
        index: ValidatorIndex,
        max_deposit: Ether) -> Gwei:
    """
    Return the effective balance (also known as "balance at stake") for a
    ``validator`` with the given ``index``.
    """
    return min(validator_balances[index], Gwei(max_deposit * GWEI_PER_ETH))


def get_fork_version(fork_data: 'ForkData',
                     slot: SlotNumber) -> int:
    """
    Return the current ``fork_version`` from the given ``fork_data`` and ``slot``.
    """
    if slot < fork_data.fork_slot:
        return fork_data.pre_fork_version
    else:
        return fork_data.post_fork_version


def get_domain(fork_data: 'ForkData',
               slot: SlotNumber,
               domain_type: SignatureDomain) -> int:
    """
    Return the domain number of the current fork and ``domain_type``.
    """
    # 2 ** 32 = 4294967296
    return get_fork_version(
        fork_data,
        slot,
    ) * 4294967296 + domain_type


@to_tuple
def get_pubkey_for_indices(validators: Sequence['ValidatorRecord'],
                           indices: Sequence[ValidatorIndex]) -> Iterable[BLSPubkey]:
    for index in indices:
        yield validators[index].pubkey


@to_tuple
def generate_aggregate_pubkeys(validators: Sequence['ValidatorRecord'],
                               vote_data: 'SlashableVoteData') -> Iterable[BLSPubkey]:
    """
    Compute the aggregate pubkey we expect based on
    the proof-of-custody indices found in the ``vote_data``.
    """
    custody_bit_0_indices = vote_data.custody_bit_0_indices
    custody_bit_1_indices = vote_data.custody_bit_1_indices
    all_indices = (custody_bit_0_indices, custody_bit_1_indices)
    get_pubkeys = functools.partial(get_pubkey_for_indices, validators)
    return map(
        bls.aggregate_pubkeys,
        map(get_pubkeys, all_indices),
    )


def verify_vote_count(vote_data: 'SlashableVoteData', max_casper_votes: int) -> bool:
    """
    Ensure we have no more than ``max_casper_votes`` in the ``vote_data``.
    """
    return vote_data.vote_count <= max_casper_votes


def verify_slashable_vote_data_signature(state: 'BeaconState',
                                         vote_data: 'SlashableVoteData') -> bool:
    """
    Ensure we have a valid aggregate signature for the ``vote_data``.
    """
    pubkeys = generate_aggregate_pubkeys(state.validator_registry, vote_data)

    messages = vote_data.messages

    signature = vote_data.aggregate_signature

    domain = get_domain(state.fork_data, vote_data.data.slot, SignatureDomain.DOMAIN_ATTESTATION)

    return bls.verify_multiple(
        pubkeys=pubkeys,
        messages=messages,
        signature=signature,
        domain=domain,
    )


def verify_slashable_vote_data(state: 'BeaconState',
                               vote_data: 'SlashableVoteData',
                               max_casper_votes: int) -> bool:
    """
    Ensure that the ``vote_data`` is properly assembled and contains the signature
    we expect from the validators we expect. Otherwise, return False as
    the ``vote_data`` is invalid.
    """
    return (
        verify_vote_count(vote_data, max_casper_votes) and
        verify_slashable_vote_data_signature(state, vote_data)
    )


def is_double_vote(attestation_data_1: 'AttestationData',
                   attestation_data_2: 'AttestationData') -> bool:
    """
    Assumes ``attestation_data_1`` is distinct from ``attestation_data_2``.

    Return True if the provided ``AttestationData`` are slashable
    due to a 'double vote'.
    """
    return attestation_data_1.slot == attestation_data_2.slot


def is_surround_vote(attestation_data_1: 'AttestationData',
                     attestation_data_2: 'AttestationData') -> bool:
    """
    Assumes ``attestation_data_1`` is distinct from ``attestation_data_2``.

    Return True if the provided ``AttestationData`` are slashable
    due to a 'surround vote'.

    Note: parameter order matters as this function only checks
    that ``attestation_data_1`` surrounds ``attestation_data_2``.
    """
    return (
        (attestation_data_1.justified_slot < attestation_data_2.justified_slot) and
        (attestation_data_2.justified_slot + 1 == attestation_data_2.slot) and
        (attestation_data_2.slot < attestation_data_1.slot)
    )
