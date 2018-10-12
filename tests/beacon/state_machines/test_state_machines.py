from eth.constants import (
    ZERO_HASH32,
)

from eth.beacon.state_machines.forks.serenity import (
    SerenityBeaconStateMachine,
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

    sm = SerenityBeaconStateMachine(chaindb, block_3)

    assert sm.crystallized_state == genesis_crystallized_state
    expect = [ZERO_HASH32] * (sm.config.CYCLE_LENGTH * 2 - 2) + \
        [genesis_block.hash] + [block_1.hash]
    expect = tuple(expect)
    assert sm.active_state.recent_block_hashes == expect
