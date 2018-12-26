from eth.beacon.db.chain import BeaconChainDB
from eth.beacon.types.blocks import BaseBeaconBlock
from eth.beacon.types.states import BeaconState


def test_demo(base_db, sample_beacon_block_params, sample_beacon_state_params, fixture_sm_class):
    chaindb = BeaconChainDB(base_db)
    state = BeaconState(**sample_beacon_state_params)
    block = BaseBeaconBlock(**sample_beacon_block_params).copy(
        slot=state.slot + 2,
    )

    sm = fixture_sm_class(chaindb, block, state)
    result_state, result_block = sm.import_block(block)

    assert state.slot == 0
    assert result_state.slot == block.slot
