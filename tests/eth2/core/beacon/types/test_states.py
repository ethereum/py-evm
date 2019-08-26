import pytest
import ssz

from eth2.beacon.tools.builder.initializer import create_mock_validator
from eth2.beacon.types.states import BeaconState


def test_defaults(sample_beacon_state_params):
    state = BeaconState(**sample_beacon_state_params)
    assert state.validators == sample_beacon_state_params["validators"]
    assert ssz.encode(state)


def test_validators_and_balances_length(sample_beacon_state_params, config):
    # When len(BeaconState.validators) != len(BeaconState.validtor_balances)
    with pytest.raises(ValueError):
        BeaconState(**sample_beacon_state_params).copy(
            validators=tuple(
                create_mock_validator(pubkey, config) for pubkey in range(10)
            )
        )


@pytest.mark.parametrize(
    "validator_index_offset, new_pubkey, new_balance",
    [(0, 5566, 100), (100, 5566, 100)],
)
def test_update_validator(
    genesis_state,
    validator_index_offset,
    validator_count,
    new_pubkey,
    new_balance,
    config,
):
    state = genesis_state
    validator = create_mock_validator(new_pubkey, config)
    validator_index = validator_count + validator_index_offset

    if validator_index < state.validator_count:
        result_state = state.update_validator(
            validator_index=validator_index, validator=validator, balance=new_balance
        )
        assert result_state.balances[validator_index] == new_balance
        assert result_state.validators[validator_index].pubkey == new_pubkey
        assert state.validators[validator_index].pubkey != new_pubkey
    else:
        with pytest.raises(IndexError):
            state.update_validator(
                validator_index=validator_index,
                validator=validator,
                balance=new_balance,
            )
