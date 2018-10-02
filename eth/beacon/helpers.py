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

from eth.utils.blake import (
    blake,
)
from eth.beacon.types.shard_and_committee import (
    ShardAndCommittee,
)
from eth.beacon.utils.random import (
    shuffle,
    split,
)


if TYPE_CHECKING:
    from eth.beacon.config import BeaconConfig  # noqa: F401
    from eth.beacon.types.active_state import ActiveState  # noqa: F401
    from eth.beacon.types.attestation_record import AttestationRecord  # noqa: F401
    from eth.beacon.types.block import Block  # noqa: F401
    from eth.beacon.types.crystallized_state import CrystallizedState  # noqa: F401
    from eth.beacon.types.validator_record import ValidatorRecord  # noqa: F401


def _get_element_from_recent_list(
        target_list: Sequence[Any],
        target_slot: int,
        slot_relative_position: int) -> Any:
    """
    Returns the element from ``target_list`` by the ``target_slot`` number,
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
    Returns the blockhash from ``ActiveState.recent_block_hashes`` by
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
                       block: 'Block',
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
    yield blake(block.hash)


@to_tuple
def get_signed_parent_hashes(recent_block_hashes: Sequence[Hash32],
                             block: 'Block',
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
    return list(old_block_hashes[shift_size:]) + [parent_hash] * parent_hash_repeat


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
    Returns committee of the given attestation.
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
    TODO: Logic changed
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
        active_validators_length: int,
        cycle_length: int,
        min_committee_size: int,
        shard_count: int) -> Tuple[int, int]:
    if active_validators_length >= cycle_length * min_committee_size:
        committees_per_slot = min(
            active_validators_length // cycle_length // (min_committee_size * 2) + 1,
            shard_count // cycle_length
        )
        slots_per_committee = 1
    else:
        committees_per_slot = 1
        slots_per_committee = 1
        bound = cycle_length * min(min_committee_size, active_validators_length)
        while(active_validators_length * slots_per_committee < bound):
            slots_per_committee *= 2

    return committees_per_slot, slots_per_committee


@to_tuple
def get_new_shuffling(seed: Hash32,
                      validators: Sequence['ValidatorRecord'],
                      dynasty: int,
                      crosslinking_start_shard: int,
                      beacon_config: 'BeaconConfig') -> Iterable[Iterable[ShardAndCommittee]]:
    """
    TODO: docstring
    NOTE: The spec might be updated to output an array rather than an array of arrays.
    """
    cycle_length = beacon_config.cycle_length
    min_committee_size = beacon_config.min_committee_size
    shard_count = beacon_config.shard_count
    active_validators = get_active_validator_indices(dynasty, validators)
    active_validators_length = len(active_validators)

    committees_per_slot, slots_per_committee = _get_shuffling_committee_slot_portions(
        active_validators_length,
        cycle_length,
        min_committee_size,
        shard_count,
    )

    shuffled_active_validator_indices = shuffle(active_validators, seed)
    validators_per_slot = split(shuffled_active_validator_indices, cycle_length)
    for slot, slot_indices in enumerate(validators_per_slot):
        shard_indices = split(slot_indices, committees_per_slot)
        shard_id_start = crosslinking_start_shard + (
            slot * committees_per_slot // slots_per_committee
        )
        yield [ShardAndCommittee(
            shard_id=(shard_id_start + j) % shard_count,
            committee=indices
        ) for j, indices in enumerate(shard_indices)]


#
# Get proposer postition
#
def get_proposer_position(parent_block: 'Block',
                          crystallized_state: 'CrystallizedState',
                          beacon_config: 'BeaconConfig') -> Tuple[int, int]:
    shards_and_committees = get_shards_and_committees_for_slot(
        crystallized_state,
        parent_block.slot_number,
        beacon_config.cycle_length,
    )
    """
    Returns the proposer index in committee and the ``shard_id``.
    """
    if len(shards_and_committees) <= 0:
        raise ValueError("shards_and_committees should not be empty.")
    shard_and_committee = shards_and_committees[0]

    # `proposer_index_in_committee` th attester in `shard_and_committee`
    # is the proposer of the parent block.
    assert shard_and_committee.committee
    proposer_index_in_committee = (
        parent_block.slot_number %
        len(shard_and_committee.committee)
    )

    return proposer_index_in_committee, shard_and_committee.shard_id
