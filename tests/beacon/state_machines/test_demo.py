import pytest

from eth.beacon.db.chain import BeaconChainDB
from eth.beacon.types.blocks import BaseBeaconBlock
from eth.beacon.types.states import BeaconState


@pytest.mark.parametrize(
    (
        'num_validators,'
        'epoch_length,'
        'target_committee_size,'
        'shard_count,'
        'latest_randao_mixes_length'
    ),
    [
        (10, 2, 2, 2, 10),
    ],
)
def test_demo(base_db, sample_beacon_block_params, genesis_state, fixture_sm_class):
    chaindb = BeaconChainDB(base_db)
    state = genesis_state

    validator_registry = []

    for validator in state.validator_registry:
        validator = validator.copy(
            randao_commitment = b"H G'`'\x11\xb8(\xab\xe7\xe3\xaf\xdf\xc7G~s\xf5\xe8\xca\x00\xe5\xea\xd8O\xaa\x1f\xe9A\x81'",
            randao_layers = 1,
        )
        validator_registry.append(validator)

    randao_reveal = b'\x0a' * 32

    block = BaseBeaconBlock(**sample_beacon_block_params).copy(
        slot = state.slot + 2,
        randao_reveal = randao_reveal,
    )

    state = genesis_state.copy(
        validator_registry = tuple(validator_registry),
    )
    
    sm = fixture_sm_class(chaindb, block, state)
    result_state, result_block = sm.import_block(block)

    assert state.slot == 0
    assert result_state.slot == block.slot
