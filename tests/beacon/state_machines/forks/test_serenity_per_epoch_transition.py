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

    # Key state variables before process_justification
    "previous_justified_slot_before,"
    "justified_slot_before,"
    "justification_bitfield_before,"
    "finalized_slot_before,"

    # Key state variables after process_justification
    "previous_justified_slot_after,"
    "justified_slot_after,"
    "justification_bitfield_after,"
    "finalized_slot_after,",
    (
        (
            # The 1st epoch transition happens in slot 64
            # Before the transition, the finalized slot, justified slot, and previous justified slot
            # should be the genesis.
            0, 10, 10, 64,
            0, 0, 0, 0,
            0, 0, 0b1, 0,
        ),
        (
            # The 2nd epoch: enough previous and current attestations justify slot 64
            10, 10, 15, 128,
            0, 0, 0b01, 0,
            0, 64, 0b11, 0,
        ),
        (
            # The 3rd epoch: enough previous and current attestations justify slot 128
            # 64 is finalized. (check_finalization `should_finalize_B3`)
            10, 10, 15, 192,
            0, 64, 0b11, 0,
            64, 128, 0b111, 64,
        ),
        (
            # The 4th epoch:
            # due to network delay
            # insufficient current attestations to justify slot 192
            10, 5, 15, 256,
            64, 128, 0b111, 64,
            128, 128, 0b1110, 64,
        ),
        (
            # The 5th epoch:
            # some attestations with justified_slot 128 arrived, and
            # no delay in current attestations.
            # Resulting 128 and 192 are justified, and 128 finalized.
            # (check_finalization `should_finalize_B2`)
            10, 10, 15, 320,
            128, 128, 0b1110, 64,
            128, 256, 0b11111, 128,
        ),
        (
            # The 6th epoch:
            # more validator joining, total_balance increased
            # but suffering from network delay, no attestation arrives.
            10, 0, 20, 384,
            128, 256, 0b11111, 128,
            256, 256, 0b111110, 128,
        ),
        (
            # The 7th epoch:
            # still suffering from network delay
            0, 0, 20, 448,
            256, 256, 0b111110, 128,
            256, 256, 0b1111100, 128,
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
