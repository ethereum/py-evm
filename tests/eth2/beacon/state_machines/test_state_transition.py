import pytest

from eth2.beacon.db.chain import BeaconChainDB
from eth2.beacon.state_machines.forks.serenity.blocks import (
    SerenityBeaconBlock,
)
from eth2.beacon.tools.builder.proposer import (
    create_mock_block,
)

from eth2._utils.merkle.normal import get_merkle_root


@pytest.mark.parametrize(
    (
        'genesis_slot,'
    ),
    [
        (0),
    ]
)
@pytest.mark.parametrize(
    (
        'num_validators,'
        'slots_per_epoch,'
        'min_attestation_inclusion_delay,'
        'target_committee_size,'
        'shard_count,'
        'state_slot,'
        'slots_per_historical_root'
    ),
    [
        (10, 10, 1, 2, 2, 2, 8192),
        # state.slot == SLOTS_PER_HISTORICAL_ROOT
        (6, 6, 1, 2, 2, 8, 8),
        # state.slot > SLOTS_PER_HISTORICAL_ROOT
        (7, 7, 1, 2, 2, 9, 8),
        # state.slot < SLOTS_PER_HISTORICAL_ROOT
        (7, 7, 1, 2, 2, 7, 8),
        # state.slot % SLOTS_PER_HISTORICAL_ROOT = 0
        (11, 4, 1, 2, 2, 16, 8),
        (16, 4, 1, 2, 2, 32, 8),
        # updated_state.slot == SLOTS_PER_HISTORICAL_ROOT
        (6, 4, 1, 2, 2, 7, 8),
        # updated_state.slot % SLOTS_PER_HISTORICAL_ROOT = 0
        (11, 4, 1, 2, 2, 15, 8),
        (16, 4, 1, 2, 2, 31, 8),
    ]
)
def test_per_slot_transition(base_db,
                             genesis_block,
                             genesis_state,
                             fixture_sm_class,
                             config,
                             state_slot,
                             keymap):
    chaindb = BeaconChainDB(base_db)
    chaindb.persist_block(genesis_block, SerenityBeaconBlock)
    chaindb.persist_state(genesis_state)

    state = genesis_state

    # Create a block
    block = create_mock_block(
        state=state,
        config=config,
        state_machine=fixture_sm_class(
            chaindb,
            genesis_block,
        ),
        block_class=SerenityBeaconBlock,
        parent_block=genesis_block,
        keymap=keymap,
        slot=state_slot,
    )

    # Store in chaindb
    chaindb.persist_block(block, SerenityBeaconBlock)

    # Get state machine instance
    sm = fixture_sm_class(
        chaindb,
        block,
    )

    # Get state transition instance
    st = sm.state_transition_class(sm.config)

    updated_state = st.per_slot_transition(state, block.previous_block_root)

    # Ensure that slot gets increased by 1
    assert updated_state.slot == state.slot + 1

    # latest_block_roots
    latest_block_roots_index = (updated_state.slot - 1) % st.config.SLOTS_PER_HISTORICAL_ROOT
    assert updated_state.latest_block_roots[latest_block_roots_index] == block.previous_block_root

    # historical_roots
    if updated_state.slot % st.config.SLOTS_PER_HISTORICAL_ROOT == 0:
        assert updated_state.historical_roots[-1] == get_merkle_root(
            updated_state.latest_block_roots
        )
    else:
        assert updated_state.historical_roots == state.historical_roots
