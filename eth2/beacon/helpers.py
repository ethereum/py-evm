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

from eth2._utils.bitfield import (
    get_bitfield_length,
    has_voted,
)
import eth2._utils.bls as bls
from eth._utils.numeric import (
    clamp,
)
from eth2.beacon._utils.random import (
    shuffle,
    split,
)

from eth2.beacon.block_committees_info import (
    BlockCommitteesInfo,
)
from eth2.beacon.constants import (
    GWEI_PER_ETH,
)
from eth2.beacon.enums import (
    SignatureDomain,
)
from eth2.beacon.types.crosslink_committees import (
    CrosslinkCommittee,
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


#
# Get crosslinks_committees or indices
#
@to_tuple
def _get_crosslink_committees_at_slot(
        state_slot: SlotNumber,
        crosslink_committees_at_slots: Sequence[Sequence[CrosslinkCommittee]],
        slot: SlotNumber,
        epoch_length: int) -> Iterable[CrosslinkCommittee]:

    earliest_slot_in_array = state_slot - (state_slot % epoch_length) - epoch_length

    if earliest_slot_in_array > slot:
        raise ValidationError(
            "earliest_slot_in_array ({}) should be less than or equal to slot ({})".format(
                earliest_slot_in_array,
                slot,
            )
        )
    if slot >= earliest_slot_in_array + epoch_length * 2:
        raise ValidationError(
            "slot ({}) should be less than "
            "(earliest_slot_in_array + epoch_length * 2) ({}), "
            "where earliest_slot_in_array={}, epoch_length={}".format(
                slot,
                earliest_slot_in_array + epoch_length * 2,
                earliest_slot_in_array,
                epoch_length,
            )
        )

    return crosslink_committees_at_slots[slot - earliest_slot_in_array]


def get_crosslink_committees_at_slot(state: 'BeaconState',
                                     slot: SlotNumber,
                                     epoch_length: int) -> Tuple[CrosslinkCommittee]:
    """
    Return the ``CrosslinkCommittee`` for the ``slot``.
    """
    return _get_crosslink_committees_at_slot(
        state_slot=state.slot,
        crosslink_committees_at_slots=state.crosslink_committees_at_slots,
        slot=slot,
        epoch_length=epoch_length,
    )


def get_active_validator_indices(validators: Sequence['ValidatorRecord'],
                                 slot: SlotNumber) -> Tuple[ValidatorIndex, ...]:
    """
    Get indices of active validators from ``validators``.
    """
    return tuple(
        ValidatorIndex(index) for index, validator in enumerate(validators)
        if validator.is_active(slot)
    )


#
# Shuffling
#
@to_tuple
def _get_crosslinks_committees_for_shard_indices(
        shard_indices: Sequence[Sequence[ValidatorIndex]],
        start_shard: ShardNumber,
        total_validator_count: int,
        shard_count: int) -> Iterable[CrosslinkCommittee]:
    """
    Return filled [CrosslinkCommittee] tuple.
    """
    for index, indices in enumerate(shard_indices):
        yield CrosslinkCommittee(
            shard=ShardNumber((start_shard + index) % shard_count),
            committee=indices,
            total_validator_count=total_validator_count,
        )


@to_tuple
def get_shuffling(*,
                  seed: Hash32,
                  validators: Sequence['ValidatorRecord'],
                  crosslinking_start_shard: ShardNumber,
                  slot: SlotNumber,
                  epoch_length: int,
                  target_committee_size: int,
                  shard_count: int) -> Iterable[Tuple[CrosslinkCommittee]]:
    """
    Return shuffled ``crosslink_committee_for_slots`` (``[[CrosslinkCommittee]]``) of
    the given active ``validators`` using ``seed`` as entropy.

    Two-dimensional:
    The first layer is ``slot`` number
        ``crosslink_committee_for_slots[slot] -> [CrosslinkCommittee]``
    The second layer is ``shard_indices`` number
        ``crosslink_committee_for_slots[slot][shard_indices] -> CrosslinkCommittee``

    Example:
        validators:
            [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
        After shuffling:
            [6, 0, 2, 12, 14, 8, 10, 4, 9, 1, 5, 13, 15, 7, 3, 11]
        Split by slot:
            [
                [6, 0, 2, 12, 14], [8, 10, 4, 9, 1], [5, 13, 15, 7, 3, 11]
            ]
        Split by shard:
            [
                [6, 0], [2, 12, 14], [8, 10], [4, 9, 1], [5, 13, 15] ,[7, 3, 11]
            ]
        Fill to output:
            [
                # slot 0
                [
                    CrosslinkCommittee(shard_id=0, committee=[6, 0]),
                    CrosslinkCommittee(shard_id=1, committee=[2, 12, 14]),
                ],
                # slot 1
                [
                    CrosslinkCommittee(shard_id=2, committee=[8, 10]),
                    CrosslinkCommittee(shard_id=3, committee=[4, 9, 1]),
                ],
                # slot 2
                [
                    CrosslinkCommittee(shard_id=4, committee=[5, 13, 15]),
                    CrosslinkCommittee(shard_id=5, committee=[7, 3, 11]),
                ],
            ]
    """
    active_validators = get_active_validator_indices(validators, slot)
    active_validators_size = len(active_validators)
    committees_per_slot = clamp(
        1,
        shard_count // epoch_length,
        active_validators_size // epoch_length // target_committee_size,
    )
    # Shuffle with seed
    shuffled_active_validator_indices = shuffle(active_validators, seed)

    # Split the shuffled list into epoch_length pieces
    validators_per_slot = split(shuffled_active_validator_indices, epoch_length)
    for index, slot_indices in enumerate(validators_per_slot):
        # Split the shuffled list into committees_per_slot pieces
        shard_indices = split(slot_indices, committees_per_slot)
        start_shard = crosslinking_start_shard + index * committees_per_slot
        yield _get_crosslinks_committees_for_shard_indices(
            shard_indices,
            start_shard,
            active_validators_size,
            shard_count,
        )


#
# Get proposer position
#
def get_block_committees_info(parent_block: 'BaseBeaconBlock',
                              state: 'BeaconState',
                              epoch_length: int) -> BlockCommitteesInfo:
    crosslinks_committees = get_crosslink_committees_at_slot(
        state,
        parent_block.slot,
        epoch_length,
    )
    """
    Return the block committees and proposer info with BlockCommitteesInfo pack.
    """
    # `proposer_index_in_committee` th attester in `crosslink_committee`
    # is the proposer of the parent block.
    try:
        crosslink_committee = crosslinks_committees[0]
    except IndexError:
        raise ValidationError("crosslinks_committees should not be empty.")

    proposer_committee_size = len(crosslink_committee.committee)
    if proposer_committee_size <= 0:
        raise ValidationError(
            "The first committee should not be empty"
        )

    proposer_index_in_committee = (
        parent_block.slot %
        proposer_committee_size
    )

    proposer_index = crosslink_committee.committee[proposer_index_in_committee]

    return BlockCommitteesInfo(
        proposer_index=proposer_index,
        proposer_shard=crosslink_committee.shard,
        proposer_committee_size=proposer_committee_size,
        crosslinks_committees=crosslinks_committees,
    )


def get_beacon_proposer_index(state: 'BeaconState',
                              slot: SlotNumber,
                              epoch_length: int) -> ValidatorIndex:
    """
    Return the beacon proposer index for the ``slot``.
    """
    crosslink_committees = get_crosslink_committees_at_slot(
        state,
        slot,
        epoch_length,
    )
    try:
        first_crosslink_committee = crosslink_committees[0]
    except IndexError:
        raise ValidationError("crosslink_committees should not be empty.")

    proposer_committee_size = len(first_crosslink_committee.committee)

    if proposer_committee_size <= 0:
        raise ValidationError(
            "The first committee should not be empty"
        )

    return first_crosslink_committee.committee[slot % len(first_crosslink_committee.committee)]


#
# Bitfields
#
@to_tuple
def get_attestation_participants(state: 'BeaconState',
                                 slot: SlotNumber,
                                 shard: ShardNumber,
                                 participation_bitfield: Bitfield,
                                 epoch_length: int) -> Iterable[ValidatorIndex]:
    """
    Return the participants' indices at the ``slot`` of shard ``shard``
    from ``participation_bitfield``.
    """
    # Find the relevant committee
    # Filter by slot
    crosslink_committees_at_slot = get_crosslink_committees_at_slot(
        state,
        slot,
        epoch_length,
    )
    # Filter by shard
    crosslink_committees = tuple(
        [
            crosslink_committee
            for crosslink_committee in crosslink_committees_at_slot
            if crosslink_committee.shard == shard
        ]
    )

    try:
        crosslink_committee = crosslink_committees[0]
    except IndexError:
        raise ValidationError("crosslink_committees should not be empty.")

    if len(participation_bitfield) != get_bitfield_length(len(crosslink_committee.committee)):
        raise ValidationError(
            'Invalid bitfield length,'
            "\texpected: %s, found: %s" % (
                get_bitfield_length(len(crosslink_committee.committee)),
                len(participation_bitfield),
            )
        )

    # Find the participating attesters in the committee
    for bitfield_index, validator_index in enumerate(crosslink_committee.committee):
        if has_voted(participation_bitfield, bitfield_index):
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

    domain = get_domain(state.fork_data, state.slot, SignatureDomain.DOMAIN_ATTESTATION)

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

    Returns True if the provided ``AttestationData`` are slashable
    due to a 'double vote'.
    """
    return attestation_data_1.slot == attestation_data_2.slot


def is_surround_vote(attestation_data_1: 'AttestationData',
                     attestation_data_2: 'AttestationData') -> bool:
    """
    Assumes ``attestation_data_1`` is distinct from ``attestation_data_2``.

    Returns True if the provided ``AttestationData`` are slashable
    due to a 'surround vote'.

    Note: parameter order matters as this function only checks
    that ``attestation_data_1`` surrounds ``attestation_data_2``.
    """
    return (
        (attestation_data_1.justified_slot < attestation_data_2.justified_slot) and
        (attestation_data_2.justified_slot + 1 == attestation_data_2.slot) and
        (attestation_data_2.slot < attestation_data_1.slot)
    )
