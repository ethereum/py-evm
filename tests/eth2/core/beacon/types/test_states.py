import pytest

import ssz

from eth2.beacon.types.states import (
    BeaconState,
)
from eth2.beacon.types.crosslinks import (
    Crosslink,
)

from eth2.beacon.tools.builder.initializer import (
    mock_validator,
)


def test_defaults(sample_beacon_state_params):
    state = BeaconState(**sample_beacon_state_params)
    assert state.validator_registry == sample_beacon_state_params['validator_registry']
    assert state.validator_registry_update_epoch == sample_beacon_state_params['validator_registry_update_epoch']  # noqa: E501
    assert ssz.encode(state)


def test_validator_registry_and_balances_length(sample_beacon_state_params, config):
    # When len(BeaconState.validator_registry) != len(BeaconState.validtor_balances)
    with pytest.raises(ValueError):
        BeaconState(**sample_beacon_state_params).copy(
            validator_registry=tuple(
                mock_validator(pubkey, config)
                for pubkey in range(10)
            ),
        )


@pytest.mark.parametrize(
    'validator_index, new_pubkey, new_balance',
    [
        (0, 5566, 100),
        (100, 5566, 100),
    ]
)
def test_update_validator(n_validators_state,
                          validator_index,
                          new_pubkey,
                          new_balance, config):
    state = n_validators_state
    validator = mock_validator(new_pubkey, config)

    if validator_index < state.num_validators:
        result_state = state.update_validator(
            validator_index=validator_index,
            validator=validator,
            balance=new_balance,
        )
        assert result_state.validator_balances[validator_index] == new_balance
        assert result_state.validator_registry[validator_index].pubkey == new_pubkey
        assert state.validator_registry[validator_index].pubkey != new_pubkey
    else:
        with pytest.raises(IndexError):
            state.update_validator(
                validator_index=validator_index,
                validator=validator,
                balance=new_balance,
            )
