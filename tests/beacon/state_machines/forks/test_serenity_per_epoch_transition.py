import pytest

from eth.beacon.state_machines.forks.serenity.epoch_transitions import process_justification
from eth.beacon.types.states import BeaconState
from eth.beacon.types.crosslink_records import CrosslinkRecord
from eth.constants import (
    ZERO_HASH32,
)


@pytest.fixture
def mock_justification_state_without_validators(
    sample_beacon_state_params,
    latest_block_roots_length,
):
    
    return BeaconState(**sample_beacon_state_params).copy(
            latest_block_roots=tuple(ZERO_HASH32 for _ in range(latest_block_roots_length)),
            justification_bitfield=b'\x00',
        )


def test_justification_without_validators(
        mock_justification_state_without_validators,
        config):
    state = process_justification(mock_justification_state_without_validators, config)
    assert state.justification_bitfield == 0b10.to_bytes(8, 'big')
