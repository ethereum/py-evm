import pytest

from eth.constants import (
    ZERO_HASH32,
)

from eth.beacon.state_machines.forks.serenity import (
    SerenityStateMachine,
)


def test_state_machine(initial_chaindb,
                       genesis_block,
                       genesis_crystallized_state):
    chaindb = initial_chaindb

    block_1 = genesis_block.copy(
        parent_hash=genesis_block.hash,
        slot_number=1,
        active_state_root=b'\x11' * 32,
    )
    chaindb.persist_block(block_1)

    block_2 = block_1.copy(
        parent_hash=block_1.hash,
        slot_number=2,
        active_state_root=b'\x22' * 32,
    )
    # canonical head is block_2
    chaindb.persist_block(block_2)

    # building block_3
    block_3 = block_2.copy(
        parent_hash=block_2.hash,
        slot_number=3,
        active_state_root=b'\x33' * 32,
    )

    sm = SerenityStateMachine(chaindb, block_3)

    assert sm.crystallized_state == genesis_crystallized_state
    expect = tuple(
        [ZERO_HASH32] * (sm.config.CYCLE_LENGTH * 2 - 2) +
        [genesis_block.hash] + [block_1.hash]
    )
    assert sm.active_state.recent_block_hashes == expect


@pytest.mark.parametrize(
    (
        'num_validators,'
        'cycle_length,min_committee_size,shard_count'
    ),
    [
        (1000, 20, 10, 100),
    ]
)
def test_import_block_one(fixture_sm_class,
                          initial_chaindb,
                          genesis_block):
    chaindb = initial_chaindb

    # Create the first block
    block_1_shell = genesis_block.copy(
        parent_hash=genesis_block.hash,
        slot_number=genesis_block.slot_number + 1,
    )
    sm = fixture_sm_class(chaindb, block_1_shell)
    active_state_1 = sm.compute_per_block_transtion(
        sm.crystallized_state,
        sm.active_state,
        block_1_shell,
        sm.chaindb,
        sm.config,
    )
    block_1 = block_1_shell.copy(
        active_state_root=active_state_1.hash,
    )
    _, _, active_state = sm.import_block(block_1)
    expect = tuple(
        [ZERO_HASH32] * (sm.config.CYCLE_LENGTH * 2 - 1) + [genesis_block.hash]
    )
    assert active_state.recent_block_hashes == expect
