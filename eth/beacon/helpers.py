from typing import (
    Any,
    Iterable,
    Sequence,
    Tuple,
    TYPE_CHECKING,
)

from eth_utils import (
    denoms,
    to_tuple,
    ValidationError,
)

from eth_typing import (
    Hash32,
)

from eth.utils.bitfield import (
    get_bitfield_length,
    has_voted,
)
from eth.utils.blake import (
    blake,
)
from eth.utils.numeric import (
    clamp,
)

from eth.beacon.block_committees_info import BlockCommitteesInfo
from eth.beacon.enums.validator_status_codes import (
    ValidatorStatusCode,
)
from eth.beacon.types.shard_committees import (
    ShardCommittee,
)
from eth.beacon.utils.random import (
    shuffle,
    split,
)


if TYPE_CHECKING:
    from eth.beacon.types.attestation_records import AttestationRecord  # noqa: F401
    from eth.beacon.types.blocks import BaseBeaconBlock  # noqa: F401
    from eth.beacon.types.states import BeaconState  # noqa: F401
    from eth.beacon.types.validator_records import ValidatorRecord  # noqa: F401


def _get_element_from_recent_list(
        target_list: Sequence[Any],
        target_slot: int,
        slot_relative_position: int) -> Any:
    """
    Return the element from ``target_list`` by the ``target_slot`` number,
    where the the element should be at ``target_slot - slot_relative_position``th
    element of the given ``target_list``.
    """
    target_list_length = len(target_list)

    if target_slot < slot_relative_position:
        raise ValueError(
            "target_slot (%s) should be greater than or equal to slot_relative_position (%s)" %
            (target_slot, slot_relative_position)
        )

    if target_slot >= slot_relative_position + target_list_length:
        raise ValueError(
            "target_slot (%s) should be less than "
            "slot_relative_position (%s) + target_list_length (%s)" %
            (target_slot, slot_relative_position, target_list_length)
        )
    return target_list[target_slot - slot_relative_position]


#
# Get block hash(es)
#
def get_block_hash(
        latest_block_hashes: Sequence[Hash32],
        current_slot: int,
        slot: int) -> Hash32:
    """
    Returns the block hash at a recent ``slot``.
    """
    slot_relative_position = current_slot - len(latest_block_hashes)
    return _get_element_from_recent_list(
        latest_block_hashes,
        slot,
        slot_relative_position,
    )


@to_tuple
def get_hashes_from_latest_block_hashes(
        latest_block_hashes: Sequence[Hash32],
        current_slot: int,
        from_slot: int,
        to_slot: int) -> Iterable[Hash32]:
    """
    Returns the block hashes between ``from_slot`` and ``to_slot``.
    """
    for slot in range(from_slot, to_slot + 1):
        yield get_block_hash(
            latest_block_hashes,
            current_slot,
            slot,
        )


#
# Get shards_committees or indices
#
@to_tuple
def _get_shard_committees_at_slot(
        latest_state_recalculation_slot: int,
        shard_committees_at_slots: Sequence[Sequence[ShardCommittee]],
        slot: int,
        epoch_length: int) -> Iterable[ShardCommittee]:
    if len(shard_committees_at_slots) != epoch_length * 2:
        raise ValueError(
            "Length of shard_committees_at_slots != epoch_length * 2"
            "\texpected: %s, found: %s" % (
                epoch_length * 2, len(shard_committees_at_slots)
            )
        )

    slot_relative_position = latest_state_recalculation_slot - epoch_length

    yield from _get_element_from_recent_list(
        shard_committees_at_slots,
        slot,
        slot_relative_position,
    )


def get_shard_committees_at_slot(state: 'BeaconState',
                                 slot: int,
                                 epoch_length: int) -> Tuple[ShardCommittee]:
    """
    Return the ``ShardCommittee`` for the ``slot``.
    """
    return _get_shard_committees_at_slot(
        latest_state_recalculation_slot=state.latest_state_recalculation_slot,
        shard_committees_at_slots=state.shard_committees_at_slots,
        slot=slot,
        epoch_length=epoch_length,
    )


def get_active_validator_indices(validators: Sequence['ValidatorRecord']) -> Tuple[int, ...]:
    """
    Get indices of active validators from ``validators``.
    """
    return tuple(
        i for i, v in enumerate(validators)
        if v.status in [ValidatorStatusCode.ACTIVE, ValidatorStatusCode.PENDING_EXIT]
    )


#
# Shuffling
#
@to_tuple
def _get_shards_committees_for_shard_indices(
        shard_indices: Sequence[Sequence[int]],
        start_shard: int,
        total_validator_count: int,
        shard_count: int) -> Iterable[ShardCommittee]:
    """
    Return filled [ShardCommittee] tuple.
    """
    for index, indices in enumerate(shard_indices):
        yield ShardCommittee(
            shard=(start_shard + index) % shard_count,
            committee=indices,
            total_validator_count=total_validator_count,
        )


@to_tuple
def get_new_shuffling(*,
                      seed: Hash32,
                      validators: Sequence['ValidatorRecord'],
                      crosslinking_start_shard: int,
                      epoch_length: int,
                      target_committee_size: int,
                      shard_count: int) -> Iterable[Iterable[ShardCommittee]]:
    """
    Return shuffled ``shard_committee_for_slots`` (``[[ShardCommittee]]``) of
    the given active ``validators`` using ``seed`` as entropy.

    Two-dimensional:
    The first layer is ``slot`` number
        ``shard_committee_for_slots[slot] -> [ShardCommittee]``
    The second layer is ``shard_indices`` number
        ``shard_committee_for_slots[slot][shard_indices] -> ShardCommittee``

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
                    ShardCommittee(shard_id=0, committee=[6, 0]),
                    ShardCommittee(shard_id=1, committee=[2, 12, 14]),
                ],
                # slot 1
                [
                    ShardCommittee(shard_id=2, committee=[8, 10]),
                    ShardCommittee(shard_id=3, committee=[4, 9, 1]),
                ],
                # slot 2
                [
                    ShardCommittee(shard_id=4, committee=[5, 13, 15]),
                    ShardCommittee(shard_id=5, committee=[7, 3, 11]),
                ],
            ]
    """
    active_validators = get_active_validator_indices(validators)
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
        yield _get_shards_committees_for_shard_indices(
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
    shards_committees = get_shard_committees_at_slot(
        state,
        parent_block.slot,
        epoch_length,
    )
    """
    Return the block committees and proposer info with BlockCommitteesInfo pack.
    """
    # `proposer_index_in_committee` th attester in `shard_committee`
    # is the proposer of the parent block.
    try:
        shard_committee = shards_committees[0]
    except IndexError:
        raise ValidationError("shards_committees should not be empty.")

    proposer_committee_size = len(shard_committee.committee)
    if proposer_committee_size <= 0:
        raise ValidationError(
            "The first committee should not be empty"
        )

    proposer_index_in_committee = (
        parent_block.slot %
        proposer_committee_size
    )

    proposer_index = shard_committee.committee[proposer_index_in_committee]

    return BlockCommitteesInfo(
        proposer_index=proposer_index,
        proposer_shard=shard_committee.shard,
        proposer_committee_size=proposer_committee_size,
        shards_committees=shards_committees,
    )


def get_beacon_proposer_index(state: 'BeaconState',
                              slot: int,
                              epoch_length: int) -> int:
    """
    Return the beacon proposer index for the ``slot``.
    """
    shard_committees = get_shard_committees_at_slot(
        state,
        slot,
        epoch_length,
    )
    try:
        first_shard_committee = shard_committees[0]
    except IndexError:
        raise ValidationError("shard_committees should not be empty.")

    proposer_committee_size = len(first_shard_committee.committee)

    if proposer_committee_size <= 0:
        raise ValidationError(
            "The first committee should not be empty"
        )

    return first_shard_committee.committee[slot % len(first_shard_committee.committee)]


#
# Bitfields
#
@to_tuple
def get_attestation_participants(state: 'BeaconState',
                                 slot: int,
                                 shard: int,
                                 participation_bitfield: bytes,
                                 epoch_length: int) -> Iterable[int]:
    """
    Return the participants' indices at the ``slot`` of shard ``shard``
    from ``participation_bitfield``.
    """
    # Find the relevant committee
    # Filter by slot
    shard_committees_at_slot = get_shard_committees_at_slot(
        state,
        slot,
        epoch_length,
    )
    # Filter by shard
    shard_committees = tuple(
        [
            shard_committee
            for shard_committee in shard_committees_at_slot
            if shard_committee.shard == shard
        ]
    )

    try:
        shard_committee = shard_committees[0]
    except IndexError:
        raise ValidationError("shard_committees should not be empty.")

    if len(participation_bitfield) != get_bitfield_length(len(shard_committee.committee)):
        raise ValidationError(
            'Invalid bitfield length,'
            "\texpected: %s, found: %s" % (
                get_bitfield_length(len(shard_committee.committee)),
                len(participation_bitfield),
            )
        )

    # Find the participating attesters in the committee
    for bitfield_index, validator_index in enumerate(shard_committee.committee):
        if has_voted(participation_bitfield, bitfield_index):
            yield validator_index


#
# Misc
#
def get_effective_balance(validator: 'ValidatorRecord', max_deposit: int) -> int:
    """
    Return the effective balance (also known as "balance at stake") for the ``validator``.
    """
    return min(validator.balance, max_deposit * denoms.gwei)


def get_new_validator_registry_delta_chain_tip(current_validator_registry_delta_chain_tip: Hash32,
                                               index: int,
                                               pubkey: int,
                                               flag: int) -> Hash32:
    """
    Compute the next hash in the validator registry delta hash chain.
    """
    return blake(
        current_validator_registry_delta_chain_tip +
        flag.to_bytes(1, 'big') +
        index.to_bytes(3, 'big') +
        # TODO: currently, we use 256-bit pubkey which is different form the spec
        pubkey.to_bytes(32, 'big')
    )
