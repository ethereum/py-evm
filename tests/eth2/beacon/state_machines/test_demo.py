import pytest

from eth2.beacon.db.chain import BeaconChainDB
from eth2.beacon.state_machines.forks.serenity.blocks import (
    SerenityBeaconBlock,
)


@pytest.mark.parametrize(
    (
        'num_validators,'
        'epoch_length,'
        'min_attestation_inclusion_delay,'
        'target_committee_size,'
        'shard_count'
    ),
    [
        (10, 10, 1, 2, 2)
    ]
)
def test_demo(base_db,
              genesis_block,
              genesis_state,
              fixture_sm_class,
              config,
              create_mock_block):
    chaindb = BeaconChainDB(base_db)
    chaindb.persist_block(genesis_block, SerenityBeaconBlock)
    chaindb.persist_state(genesis_state)

    state = genesis_state

    block = create_mock_block(
        state=state,
        block_class=SerenityBeaconBlock,
        parent_block=genesis_block,
        config=config,
        slot=state.slot + 2,
    )

    # Store in chaindb
    chaindb.persist_block(block, SerenityBeaconBlock)

    # Get state machine instance
    sm = fixture_sm_class(
        chaindb,
        block,
        parent_block_class=SerenityBeaconBlock,
    )
    result_state, _ = sm.import_block(block)
    chaindb.persist_state(result_state)

    assert state.slot == 0
    assert result_state.slot == block.slot
    assert isinstance(sm.block, SerenityBeaconBlock)
