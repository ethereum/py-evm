from itertools import (
    repeat,
)

from typing import (
    Any,
    Iterable,
    Sequence,
    Tuple,
    TYPE_CHECKING,
)

from eth_utils import (
    to_tuple,
)

from eth_typing import (
    Hash32,
)

from eth.utils.numeric import (
    clamp,
)

from eth.beacon.block_committees_info import BlockCommitteesInfo
from eth.beacon.types.shard_and_committees import (
    ShardAndCommittee,
)
from eth.beacon.utils.random import (
    shuffle,
    split,
)


if TYPE_CHECKING:
    from eth.beacon.types.active_states import ActiveState  # noqa: F401
    from eth.beacon.types.attestation_records import AttestationRecord  # noqa: F401
    from eth.beacon.types.blocks import BaseBeaconBlock  # noqa: F401
    from eth.beacon.types.crystallized_states import CrystallizedState  # noqa: F401
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
        recent_block_hashes: Sequence[Hash32],
        current_block_slot_number: int,
        slot: int,
        cycle_length: int) -> Hash32:
    """
    Return the blockhash from ``ActiveState.recent_block_hashes`` by
    ``current_block_slot_number``.
    """
    if len(recent_block_hashes) != cycle_length * 2:
        raise ValueError(
            "Length of recent_block_hashes != cycle_length * 2"
            "\texpected: %s, found: %s" % (
                cycle_length * 2, len(recent_block_hashes)
            )
        )

    slot_relative_position = current_block_slot_number - cycle_length * 2
    return _get_element_from_recent_list(
        recent_block_hashes,
        slot,
        slot_relative_position,
    )


@to_tuple
def get_hashes_from_recent_block_hashes(
        recent_block_hashes: Sequence[Hash32],
        current_block_slot_number: int,
        from_slot: int,
        to_slot: int,
        cycle_length: int) -> Iterable[Hash32]:
    """
    Returns the block hashes between ``from_slot`` and ``to_slot``.
    """
    for slot in range(from_slot, to_slot + 1):
        yield get_block_hash(
            recent_block_hashes,
            current_block_slot_number,
            slot,
            cycle_length,
        )


@to_tuple
def get_hashes_to_sign(recent_block_hashes: Sequence[Hash32],
                       block: 'BaseBeaconBlock',
                       cycle_length: int) -> Iterable[Hash32]:
    """
    Given the head block to attest to, collect the list of hashes to be
    signed in the attestation.
    """
    yield from get_hashes_from_recent_block_hashes(
        recent_block_hashes,
        block.slot_number,
        from_slot=block.slot_number - cycle_length + 1,
        to_slot=block.slot_number - 1,
        cycle_length=cycle_length,
    )
    yield block.hash


@to_tuple
def get_signed_parent_hashes(recent_block_hashes: Sequence[Hash32],
                             block: 'BaseBeaconBlock',
                             attestation: 'AttestationRecord',
                             cycle_length: int) -> Iterable[Hash32]:
    """
    Given an attestation and the block they were included in,
    the list of hashes that were included in the signature.
    """
    yield from get_hashes_from_recent_block_hashes(
        recent_block_hashes,
        block.slot_number,
        from_slot=attestation.slot - cycle_length + 1,
        to_slot=attestation.slot - len(attestation.oblique_parent_hashes),
        cycle_length=cycle_length,
    )
    yield from attestation.oblique_parent_hashes


@to_tuple
def get_new_recent_block_hashes(old_block_hashes: Sequence[Hash32],
                                parent_slot: int,
                                current_slot: int,
                                parent_hash: Hash32) -> Iterable[Hash32]:

    shift_size = current_slot - parent_slot
    parent_hash_repeat = min(shift_size, len(old_block_hashes))
    yield from old_block_hashes[shift_size:]
    yield from repeat(parent_hash, parent_hash_repeat)


#
# Get shards_and_committees or indices
#
@to_tuple
def get_shards_and_committees_for_slot(
        crystallized_state: 'CrystallizedState',
        slot: int,
        cycle_length: int) -> Iterable[ShardAndCommittee]:
    if len(crystallized_state.shard_and_committee_for_slots) != cycle_length * 2:
        raise ValueError(
            "Length of shard_and_committee_for_slots != cycle_length * 2"
            "\texpected: %s, found: %s" % (
                cycle_length * 2, len(crystallized_state.shard_and_committee_for_slots)
            )
        )

    slot_relative_position = crystallized_state.last_state_recalc - cycle_length

    yield from _get_element_from_recent_list(
        crystallized_state.shard_and_committee_for_slots,
        slot,
        slot_relative_position,
    )


@to_tuple
def get_attestation_indices(crystallized_state: 'CrystallizedState',
                            attestation: 'AttestationRecord',
                            cycle_length: int) -> Iterable[int]:
    """
    Return committee of the given attestation.
    """
    shard_id = attestation.shard_id

    shards_and_committees_for_slot = get_shards_and_committees_for_slot(
        crystallized_state,
        attestation.slot,
        cycle_length,
    )

    for shard_and_committee in shards_and_committees_for_slot:
        if shard_and_committee.shard_id == shard_id:
            yield from shard_and_committee.committee


@to_tuple
def get_active_validator_indices(dynasty: int,
                                 validators: Iterable['ValidatorRecord']) -> Iterable[int]:
    """
    TODO: Logic changed in the latest spec, will have to update when we add validator
    rotation logic.
    https://github.com/ethereum/eth2.0-specs/commit/52cf7f943dc99cfd27db9fb2c03c692858e2a789#diff-a08ecec277db4a6ed0b3635cfadc9af1  # noqa: E501
    """
    o = []
    for index, validator in enumerate(validators):
        if (validator.start_dynasty <= dynasty and dynasty < validator.end_dynasty):
            o.append(index)
    return o


#
# Shuffling
#
def _get_shuffling_committee_slot_portions(
        active_validators_size: int,
        cycle_length: int,
        min_committee_size: int,
        shard_count: int) -> Tuple[int, int]:
    """
    Return committees number per slot and slots number per committee.
    """
    # If there are enough active validators to form committees for every slot
    if active_validators_size >= cycle_length * min_committee_size:
        # One slot can be attested by many committees, but not more than shard_count // cycle_length
        committees_per_slot = min(
            active_validators_size // cycle_length // (min_committee_size * 2) + 1,
            shard_count // cycle_length
        )
        # One committee only has to attest one slot
        slots_per_committee = 1
    else:
        # One slot can only be asttested by one committee
        committees_per_slot = 1
        # One committee has to asttest more than one slot
        slots_per_committee = 1
        bound = cycle_length * min(min_committee_size, active_validators_size)
        while(active_validators_size * slots_per_committee < bound):
            slots_per_committee *= 2

    return committees_per_slot, slots_per_committee


@to_tuple
def _get_shards_and_committees_for_shard_indices(
        shard_indices: Sequence[Sequence[int]],
        shard_id_start: int,
        shard_count: int) -> Iterable[ShardAndCommittee]:
    """
    Returns filled [ShardAndCommittee] tuple.
    """
    for index, indices in enumerate(shard_indices):
        yield ShardAndCommittee(
            shard_id=(shard_id_start + index) % shard_count,
            committee=indices
        )


@to_tuple
def get_new_shuffling(*,
                      seed: Hash32,
                      validators: Sequence['ValidatorRecord'],
                      dynasty: int,
                      crosslinking_start_shard: int,
                      cycle_length: int,
                      min_committee_size: int,
                      shard_count: int) -> Iterable[Iterable[ShardAndCommittee]]:
    """
    Return shuffled ``shard_and_committee_for_slots`` (``[[ShardAndCommittee]]``) of
    the given active ``validators``.

    Two-dimensional:
    The first layer is ``slot`` number
        ``shard_and_committee_for_slots[slot] -> [ShardAndCommittee]``
    The second layer is ``shard_indices`` number
        ``shard_and_committee_for_slots[slot][shard_indices] -> ShardAndCommittee``

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
                    ShardAndCommittee(shard_id=0, committee=[6, 0]),
                    ShardAndCommittee(shard_id=1, committee=[2, 12, 14]),
                ],
                # slot 1
                [
                    ShardAndCommittee(shard_id=2, committee=[8, 10]),
                    ShardAndCommittee(shard_id=3, committee=[4, 9, 1]),
                ],
                # slot 2
                [
                    ShardAndCommittee(shard_id=4, committee=[5, 13, 15]),
                    ShardAndCommittee(shard_id=5, committee=[7, 3, 11]),
                ],
            ]

    NOTE: The spec might be updated to output an array rather than an array of arrays.
    """
    active_validators = get_active_validator_indices(dynasty, validators)
    active_validators_size = len(active_validators)
    committees_per_slot = clamp(
        1,
        shard_count // cycle_length,
        active_validators_size // cycle_length // (min_committee_size * 2) + 1,
    )
    shuffled_active_validator_indices = shuffle(active_validators, seed)

    # Split the shuffled list into cycle_length pieces
    validators_per_slot = split(shuffled_active_validator_indices, cycle_length)
    for index, slot_indices in enumerate(validators_per_slot):
        # Split the shuffled list into committees_per_slot pieces
        shard_indices = split(slot_indices, committees_per_slot)
        shard_id_start = crosslinking_start_shard + index * committees_per_slot
        yield _get_shards_and_committees_for_shard_indices(
            shard_indices,
            shard_id_start,
            shard_count,
        )


#
# Get proposer postition
#
def get_block_committees_info(parent_block: 'BaseBeaconBlock',
                              crystallized_state: 'CrystallizedState',
                              cycle_length: int) -> BlockCommitteesInfo:
    shards_and_committees = get_shards_and_committees_for_slot(
        crystallized_state,
        parent_block.slot_number,
        cycle_length,
    )
    """
    Return the block committees and proposer info with BlockCommitteesInfo pack.
    """
    # `proposer_index_in_committee` th attester in `shard_and_committee`
    # is the proposer of the parent block.
    try:
        shard_and_committee = shards_and_committees[0]
    except IndexError:
        raise ValueError("shards_and_committees should not be empty.")

    proposer_committee_size = len(shard_and_committee.committee)
    if proposer_committee_size <= 0:
        raise ValueError(
            "The first committee should not be empty"
        )

    proposer_index_in_committee = (
        parent_block.slot_number %
        proposer_committee_size
    )

    # The index in CrystallizedState.validators
    proposer_index = shard_and_committee.committee[proposer_index_in_committee]

    return BlockCommitteesInfo(
        proposer_index=proposer_index,
        proposer_index_in_committee=proposer_index_in_committee,
        proposer_shard_id=shard_and_committee.shard_id,
        proposer_committee_size=proposer_committee_size,
        shards_and_committees=shards_and_committees,
    )
