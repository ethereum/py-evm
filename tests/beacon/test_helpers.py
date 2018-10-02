import pytest

from eth.beacon.types.active_state import ActiveState
from eth.beacon.types.shard_and_committee import ShardAndCommittee
from eth.beacon.helpers import (
    get_new_shuffling,
    get_shards_and_committees_for_slot,
    get_block_hash,
    get_proposer_position,
)

from tests.beacon.helpers import (
    get_pseudo_chain,
)


#
# Get block hashes
#
@pytest.mark.parametrize(
    (
        'current_block_number,slot,success'
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
        slot,
        success,
        beacon_config):
    cycle_length = beacon_config.cycle_length

    blocks = get_pseudo_chain(cycle_length * 3, genesis_block)
    recent_block_hashes = [
        b'\x00' * 32
        for i
        in range(cycle_length * 2 - current_block_number)
    ] + [block.hash for block in blocks[:current_block_number]]
    active_state = ActiveState(
        recent_block_hashes=recent_block_hashes,
    )
    current_block = blocks[current_block_number]

    if success:
        block_hash = get_block_hash(
            active_state,
            current_block,
            slot,
            beacon_config,
        )
        assert block_hash == blocks[slot].hash
    else:
        with pytest.raises(AssertionError):
            get_block_hash(
                active_state,
                current_block,
                slot,
                beacon_config,
            )


def test_get_hashes_from_active_state():
    # TODO
    pass


def test_get_hashes_to_sign():
    # TODO
    pass


def test_get_signed_parent_hashes():
    # TODO
    pass


def test_get_new_recent_block_hashes():
    # TODO
    pass


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
def test_get_shards_and_committees_for_slot(
        genesis_crystallized_state,
        num_validators,
        slot,
        success,
        beacon_config):
    crystallized_state = genesis_crystallized_state

    if success:
        shards_and_committees_for_slot = get_shards_and_committees_for_slot(
            crystallized_state,
            slot,
            beacon_config,
        )
        assert len(shards_and_committees_for_slot) > 0
    else:
        with pytest.raises(AssertionError):
            get_shards_and_committees_for_slot(
                crystallized_state,
                slot,
                beacon_config,
            )


def test_get_attestation_indices():
    # TODO
    pass


#
# Shuffling
#
def test_shuffle_remaining_is_zero():
    # TODO
    pass


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
