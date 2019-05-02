import pytest

import ssz

from eth2.beacon.types.states import (
    BeaconState,
)
from eth2.beacon.types.crosslink_records import (
    CrosslinkRecord,
)

from tests.eth2.beacon.helpers import (
    mock_validator_record,
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
                mock_validator_record(pubkey, config)
                for pubkey in range(10)
            ),
        )


@pytest.mark.parametrize(
    'expected', [(0), (1)]
)
def test_num_validators(expected,
                        max_deposit_amount,
                        filled_beacon_state,
                        config):
    state = filled_beacon_state.copy(
        validator_registry=tuple(
            mock_validator_record(
                pubkey,
                config,
            )
            for pubkey in range(expected)
        ),
        validator_balances=(max_deposit_amount,) * expected,
    )

    assert state.num_validators == expected


@pytest.mark.parametrize(
    'expected', [(0), (1), (5)]
)
def test_num_crosslink_records(expected,
                               sample_crosslink_record_params,
                               filled_beacon_state):
    crosslink_records = [
        CrosslinkRecord(**sample_crosslink_record_params)
        for i in range(expected)
    ]
    state = filled_beacon_state.copy(
        latest_crosslinks=crosslink_records,
    )

    assert state.num_crosslinks == expected


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
    validator = mock_validator_record(new_pubkey, config)

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
