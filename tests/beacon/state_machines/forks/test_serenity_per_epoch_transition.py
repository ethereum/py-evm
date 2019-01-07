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
    assert state.justification_bitfield == 0b11.to_bytes(8, 'big')


@pytest.mark.parametrize(
    "previous_epoch_boundary_attesting_balance,"
    "current_epoch_boundary_attesting_balance,"
    "total_balance,"
    "slot,"

    "previous_justified_slot_before,"
    "justified_slot_before,"
    "justification_bitfield_before,"
    "finalized_slot_before,"

    "previous_justified_slot_after,"
    "justified_slot_after,"
    "justification_bitfield_after,"
    "finalized_slot_after,",
    (
        (
            # The first epoch transition happens in slot 64
            # Before the transition, the finalized slot, justified slot, and previous justified slot
            # should be the genesis.
            0, 10, 10, 64,
            0, 0, 0, 0,
            0, 0, 0b1, 0,
        ),
        (
            10, 10, 15, 128,
            0, 0, 0b01, 0,
            0, 64, 0b11, 0,
        ),
        (
            10, 10, 15, 192,
            0, 64, 0b11, 0,
            64, 128, 0b111, 64,
        ),
    ),
)
def test_justification(
    monkeypatch,
    config,
    sample_beacon_state_params,
    latest_block_roots_length,
    previous_epoch_boundary_attesting_balance,
    current_epoch_boundary_attesting_balance,
    total_balance,
    slot,
    previous_justified_slot_before,
    justified_slot_before,
    justification_bitfield_before,
    finalized_slot_before,
    previous_justified_slot_after,
    justified_slot_after,
    justification_bitfield_after,
    finalized_slot_after,


):
    from eth.beacon.state_machines.forks.serenity import epoch_transitions

    def mock_epoch_boundary_attesting_balances(state, config):
        return previous_epoch_boundary_attesting_balance, current_epoch_boundary_attesting_balance

    def mock_get_total_balance(validator_registry,
                               validator_balances,
                               max_deposits):
        return total_balance

    with monkeypatch.context() as m:
        m.setattr(
            epoch_transitions,
            'get_epoch_boundary_attesting_balances',
            mock_epoch_boundary_attesting_balances,
        )
        m.setattr(
            epoch_transitions,
            'get_total_balance',
            mock_get_total_balance,
        )

        state_before = BeaconState(**sample_beacon_state_params).copy(
            slot=slot,
            latest_block_roots=tuple(ZERO_HASH32 for _ in range(latest_block_roots_length)),
            previous_justified_slot=previous_justified_slot_before,
            justified_slot=justified_slot_before,
            justification_bitfield=justification_bitfield_before.to_bytes(8, 'big'),
            finalized_slot=finalized_slot_before,
        )

        state_after = process_justification(state_before, config)

        assert state_after.previous_justified_slot == previous_justified_slot_after
        assert state_after.justified_slot == justified_slot_after
        assert state_after.justification_bitfield == justification_bitfield_after.to_bytes(8, 'big')
        assert state_after.finalized_slot == finalized_slot_after
