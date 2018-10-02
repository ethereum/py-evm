import pytest

from eth.beacon.types.attestation_record import AttestationRecord
from eth.beacon.types.shard_and_committee import ShardAndCommittee
from eth.beacon.helpers import (
    get_attestation_indices,
    get_block_hash,
    get_element_from_recent_list,
    get_hashes_from_recent_block_hashes,
    get_hashes_to_sign,
    get_new_shuffling,
    get_shards_and_committees_for_slot,
    get_signed_parent_hashes,
    get_proposer_position,
)
from eth.utils.blake import (
    blake,
)

from tests.beacon.helpers import (
    get_pseudo_chain,
)


def generate_mock_recent_block_hashes(
        genesis_block,
        current_block_number,
        cycle_length):
    chain_length = (current_block_number // cycle_length + 1) * cycle_length
    blocks = get_pseudo_chain(chain_length, genesis_block)
    recent_block_hashes = [
        b'\x00' * 32
        for i
        in range(cycle_length * 2 - current_block_number)
    ] + [block.hash for block in blocks[:current_block_number]]
    return blocks, recent_block_hashes


@pytest.mark.parametrize(
    (
        'target_list,target_slot,slot_relative_position,success,result'
    ),
    [
        ([i for i in range(5)], 10, 7, True, 3),
        ([], 1, 1, False, -1),
        # target_slot < slot_relative_position
        ([i for i in range(5)], 1, 2, False, -1),
        # target_slot >= slot_relative_position + target_list_length
        ([i for i in range(5)], 6, 1, False, -1),
    ],
)
def test_get_element_from_recent_list(target_list,
                                      target_slot,
                                      slot_relative_position,
                                      success,
                                      result):
    if success:
        assert result == get_element_from_recent_list(
            target_list,
            target_slot,
            slot_relative_position,
        )
    else:
        with pytest.raises(ValueError):
            get_element_from_recent_list(
                target_list,
                target_slot,
                slot_relative_position,
            )


#
# Get block hashes
#
@pytest.mark.parametrize(
    (
        'current_block_number,target_slot,success'
    ),
    [
        (10, 0, True),
        (10, 9, True),
        (10, 10, False),
        (128, 0, True),
        (128, 127, True),
        (128, 128, False),
    ],
)
def test_get_block_hash(
        genesis_block,
        current_block_number,
        target_slot,
        success,
        beacon_config):
    cycle_length = beacon_config.cycle_length

    blocks, recent_block_hashes = generate_mock_recent_block_hashes(
        genesis_block,
        current_block_number,
        cycle_length,
    )

    if success:
        block_hash = get_block_hash(
            recent_block_hashes,
            current_block_number,
            target_slot,
            cycle_length,
        )
        assert block_hash == blocks[target_slot].hash
    else:
        with pytest.raises(ValueError):
            get_block_hash(
                recent_block_hashes,
                current_block_number,
                target_slot,
                cycle_length,
            )


@pytest.mark.parametrize(
    (
        'cycle_length,current_block_slot_number,from_slot,to_slot'
    ),
    [
        (20, 10, 2, 7),
        (20, 30, 10, 20),
    ],
)
def test_get_hashes_from_recent_block_hashes(
        genesis_block,
        current_block_slot_number,
        from_slot,
        to_slot,
        cycle_length):
    _, recent_block_hashes = generate_mock_recent_block_hashes(
        genesis_block,
        current_block_slot_number,
        cycle_length,
    )

    result = get_hashes_from_recent_block_hashes(
        recent_block_hashes,
        current_block_slot_number,
        from_slot,
        to_slot,
        cycle_length,
    )
    assert len(result) == to_slot - from_slot + 1


def test_get_hashes_to_sign(genesis_block, beacon_config):
    cycle_length = beacon_config.cycle_length
    current_block_slot_number = 1
    blocks, recent_block_hashes = generate_mock_recent_block_hashes(
        genesis_block,
        current_block_slot_number,
        cycle_length,
    )

    block = blocks[current_block_slot_number]
    result = get_hashes_to_sign(
        recent_block_hashes,
        block,
        cycle_length,
    )
    assert len(result) == cycle_length
    assert result[-1] == blake(block.hash)


def test_get_new_recent_block_hashes(genesis_block,
                                     beacon_config,
                                     sample_attestation_record_params):
    cycle_length = beacon_config.cycle_length
    current_block_slot_number = 15
    blocks, recent_block_hashes = generate_mock_recent_block_hashes(
        genesis_block,
        current_block_slot_number,
        cycle_length,
    )

    block = blocks[current_block_slot_number]
    attestation = AttestationRecord(**sample_attestation_record_params)
    oblique_parent_hashes = [b'\x77' * 32]
    attestation = attestation.copy(
        slot=10,
        oblique_parent_hashes=oblique_parent_hashes,
    )
    result = get_signed_parent_hashes(
        recent_block_hashes,
        block,
        attestation,
        cycle_length,
    )
    assert len(result) == cycle_length
    assert result[-1] == oblique_parent_hashes[-1]


#
# Get shards_and_committees or indices
#
@pytest.mark.parametrize(
    (
        'num_validators,slot,success'
    ),
    [
        (100, 0, True),
        (100, 63, True),
        (100, 64, False),
    ],
)
def test_get_shard_and_committee_for_slot(
        genesis_crystallized_state,
        num_validators,
        slot,
        success,
        cycle_length):
    crystallized_state = genesis_crystallized_state

    if success:
        shards_and_committees_for_slot = get_shards_and_committees_for_slot(
            crystallized_state,
            slot,
            cycle_length,
        )
        assert len(shards_and_committees_for_slot) > 0
        assert len(shards_and_committees_for_slot[0].committee) > 0
    else:
        with pytest.raises(ValueError):
            get_shards_and_committees_for_slot(
                crystallized_state,
                slot,
                cycle_length,
            )


@pytest.mark.parametrize(
    (
        'num_validators,max_validator_count,cycle_length,'
        'min_committee_size,shard_count'
    ),
    [
        (1000, 1000, 20, 10, 100),
    ],
)
def test_get_attestation_indices(genesis_crystallized_state,
                                 sample_attestation_record_params,
                                 min_committee_size,
                                 beacon_config):
    attestation = AttestationRecord(**sample_attestation_record_params)
    attestation = attestation.copy(
        slot=0,
        shard_id=0,
    )

    attestation_indices = get_attestation_indices(
        genesis_crystallized_state,
        attestation,
        beacon_config.cycle_length,
    )
    assert len(attestation_indices) >= min_committee_size


#
# Shuffling
#
@pytest.mark.parametrize(
    (
        'num_validators,max_validator_count,cycle_length,'
        'min_committee_size,shard_count'
    ),
    [
        (1000, 1000, 20, 10, 100),
        (100, 500, 50, 10, 10),
        (20, 100, 10, 3, 10),
    ],
)
def test_get_new_shuffling_is_complete(genesis_validators, beacon_config):
    dynasty = 1

    shuffling = get_new_shuffling(
        b'\x35' * 32,
        genesis_validators,
        dynasty,
        0,
        beacon_config
    )

    assert len(shuffling) == beacon_config.cycle_length
    validators = set()
    shards = set()
    for slot_indices in shuffling:
        for shard_and_committee in slot_indices:
            shards.add(shard_and_committee.shard_id)
            for vi in shard_and_committee.committee:
                validators.add(vi)

    # assert len(shards) == beacon_config.shard_count
    assert len(validators) == len(genesis_validators)


@pytest.mark.parametrize(
    (
        'num_validators,max_validator_count,cycle_length,'
        'min_committee_size,shard_count'
    ),
    [
        (1000, 1000, 20, 10, 100),
        (100, 500, 50, 10, 10),
        (20, 100, 10, 3, 10),
    ],
)
def test_get_new_shuffling_handles_shard_wrap(genesis_validators, beacon_config):
    dynasty = 1

    shuffling = get_new_shuffling(
        b'\x35' * 32,
        genesis_validators,
        dynasty,
        beacon_config.shard_count - 1,
        beacon_config
    )

    # shard assignments should wrap around to 0 rather than continuing to SHARD_COUNT
    for slot_indices in shuffling:
        for shard_and_committee in slot_indices:
            assert shard_and_committee.shard_id < beacon_config.shard_count


def test_get_new_shuffling_large_validator_size():
    # TODO
    pass


#
# Get proposer postition
#
@pytest.mark.parametrize(
    (
        'committee,parent_block_number,result_proposer_index_in_committee'
    ),
    [
        ([0, 1, 2, 3], 0, 0),
        ([0, 1, 2, 3], 2, 2),
        ([0, 1, 2, 3], 11, 3),
    ],
)
def test_get_proposer_position(monkeypatch,
                               genesis_block,
                               genesis_crystallized_state,
                               committee,
                               parent_block_number,
                               result_proposer_index_in_committee,
                               beacon_config):
    from eth.beacon import helpers

    def mock_get_shards_and_committees_for_slot(parent_block,
                                                crystallized_state,
                                                beacon_config):
        return [
            ShardAndCommittee(shard_id=1, committee=committee),
        ]

    monkeypatch.setattr(
        helpers,
        'get_shards_and_committees_for_slot',
        mock_get_shards_and_committees_for_slot
    )

    parent_block = genesis_block
    parent_block = genesis_block.copy(
        slot_number=parent_block_number,
    )

    proposer_index_in_committee, _ = get_proposer_position(
        parent_block,
        genesis_crystallized_state,
        beacon_config,
    )

    assert proposer_index_in_committee == result_proposer_index_in_committee
