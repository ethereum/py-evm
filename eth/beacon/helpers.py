from typing import (
    Iterable,
    Any,
    List,
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


if TYPE_CHECKING:
    from eth.beacon.config import BeaconConfig  # noqa: F401
    from eth.beacon.types.active_state import ActiveState  # noqa: F401
    from eth.beacon.types.attestation_record import AttestationRecord  # noqa: F401
    from eth.beacon.types.block import Block  # noqa: F401
    from eth.beacon.types.crystallized_state import CrystallizedState  # noqa: F401
    from eth.beacon.types.validator_record import ValidatorRecord  # noqa: F401


#
# Get block hashes
#
def get_block_hash(
        active_state: 'ActiveState',
        current_block: 'Block',
        slot: int,
        beacon_config: 'BeaconConfig') -> Hash32:
    cycle_length = beacon_config.cycle_length

    sback = current_block.slot_number - cycle_length * 2
    assert sback <= slot < sback + cycle_length * 2
    return active_state.recent_block_hashes[slot - sback]


def get_hashes_from_active_state(active_state: 'ActiveState',
                                 block: 'Block',
                                 from_slot: int,
                                 to_slot: int,
                                 beacon_config: 'BeaconConfig') -> List[Hash32]:
    hashes = [
        get_block_hash(
            active_state,
            block,
            slot,
            beacon_config,
        )
        for slot
        in range(from_slot, to_slot + 1)
    ]
    return hashes


def get_hashes_to_sign(active_state: 'ActiveState',
                       block: 'Block',
                       beacon_config: 'BeaconConfig') -> List[Hash32]:
    """
    Given the head block to attest to, collect the list of hashes to be
    signed in the attestation
    """
    cycle_length = beacon_config.cycle_length

    hashes = get_hashes_from_active_state(
        active_state,
        block,
        from_slot=block.slot_number - cycle_length + 1,
        to_slot=block.slot_number - 1,
        beacon_config=beacon_config,
    ) + [blake(block.hash)]

    return hashes


def get_signed_parent_hashes(active_state: 'ActiveState',
                             block: 'Block',
                             attestation: 'AttestationRecord',
                             beacon_config: 'BeaconConfig') -> List[Hash32]:
    """
    Given an attestation and the block they were included in,
    the list of hashes that were included in the signature
    """
    cycle_length = beacon_config.cycle_length
    parent_hashes = get_hashes_from_active_state(
        active_state,
        block,
        from_slot=attestation.slot - cycle_length + 1,
        to_slot=attestation.slot - len(attestation.oblique_parent_hashes),
        beacon_config=beacon_config,
    ) + attestation.oblique_parent_hashes

    return parent_hashes


def get_new_recent_block_hashes(old_block_hashes: List[Hash32],
                                parent_slot: int,
                                current_slot: int,
                                parent_hash: Hash32) -> List[Hash32]:
    d = current_slot - parent_slot
    return old_block_hashes[d:] + [parent_hash] * min(d, len(old_block_hashes))


#
# Get shards_and_committees or indices
#
def get_shards_and_committees_for_slot(
        crystallized_state: 'CrystallizedState',
        slot: int,
        beacon_config: 'BeaconConfig') -> List[ShardAndCommittee]:
    cycle_length = beacon_config.cycle_length

    start = crystallized_state.last_state_recalc - cycle_length
    assert start <= slot < start + cycle_length * 2
    return crystallized_state.shard_and_committee_for_slots[slot - start]


def get_attestation_indices(crystallized_state: 'CrystallizedState',
                            attestation: 'AttestationRecord',
                            beacon_config: 'BeaconConfig') -> List[int]:
    shard_id = attestation.shard_id

    filtered_shards_and_committees_for_slot = list(
        filter(
            lambda x: x.shard_id == shard_id,
            get_shards_and_committees_for_slot(
                crystallized_state,
                attestation.slot,
                beacon_config=beacon_config,
            )
        )
    )

    attestation_indices = []  # type: List[int]
    if filtered_shards_and_committees_for_slot:
        attestation_indices = filtered_shards_and_committees_for_slot[0].committee

    return attestation_indices


@to_tuple
def get_active_validator_indices(dynasty: int,
                                 validators: Iterable['ValidatorRecord']) -> List[int]:
    o = []
    for index, validator in enumerate(validators):
        if (validator.start_dynasty <= dynasty and dynasty < validator.end_dynasty):
            o.append(index)
    return o


#
# Shuffling
#
def shuffle(lst: List[Any],
            seed: Hash32) -> List[Any]:
    lst_count = len(lst)
    assert lst_count <= 16777216
    o = [x for x in lst]
    source = seed
    i = 0
    while i < lst_count:
        source = blake(source)
        for pos in range(0, 30, 3):
            m = int.from_bytes(source[pos:pos + 3], 'big')
            remaining = lst_count - i
            if remaining == 0:
                break
            rand_max = 16777216 - 16777216 % remaining
            if m < rand_max:
                replacement_pos = (m % remaining) + i
                o[i], o[replacement_pos] = o[replacement_pos], o[i]
                i += 1
    return o


def split(lst: List[Any], N: int) -> List[Any]:
    list_length = len(lst)
    return [
        lst[(list_length * i // N): (list_length * (i + 1) // N)] for i in range(N)
    ]


def get_new_shuffling(seed: Hash32,
                      validators: List['ValidatorRecord'],
                      dynasty: int,
                      crosslinking_start_shard: int,
                      beacon_config: 'BeaconConfig') -> List[List[ShardAndCommittee]]:
    cycle_length = beacon_config.cycle_length
    min_committee_size = beacon_config.min_committee_size
    shard_count = beacon_config.shard_count
    avs = get_active_validator_indices(dynasty, validators)
    if len(avs) >= cycle_length * min_committee_size:
        committees_per_slot = len(avs) // cycle_length // (min_committee_size * 2) + 1
        slots_per_committee = 1
    else:
        committees_per_slot = 1
        slots_per_committee = 1
        while (len(avs) * slots_per_committee < cycle_length * min_committee_size and
               slots_per_committee < cycle_length):
            slots_per_committee *= 2
    o = []

    shuffled_active_validator_indices = shuffle(avs, seed)
    validators_per_slot = split(shuffled_active_validator_indices, cycle_length)
    for slot, slot_indices in enumerate(validators_per_slot):
        shard_indices = split(slot_indices, committees_per_slot)
        shard_id_start = crosslinking_start_shard + (
            slot * committees_per_slot // slots_per_committee
        )
        o.append([ShardAndCommittee(
            shard_id=(shard_id_start + j) % shard_count,
            committee=indices
        ) for j, indices in enumerate(shard_indices)])
    return o


#
# Get proposer postition
#
def get_proposer_position(parent_block: 'Block',
                          crystallized_state: 'CrystallizedState',
                          beacon_config: 'BeaconConfig') -> Tuple[int, int]:
    shards_and_committees = get_shards_and_committees_for_slot(
        crystallized_state,
        parent_block.slot_number,
        beacon_config=beacon_config,
    )
    assert shards_and_committees
    shard_and_committee = shards_and_committees[0]

    # `proposer_index_in_committee` th attester in `shard_and_committee`
    # is the proposer of the parent block.
    assert shard_and_committee.committee
    proposer_index_in_committee = (
        parent_block.slot_number %
        len(shard_and_committee.committee)
    )

    return proposer_index_in_committee, shard_and_committee.shard_id
