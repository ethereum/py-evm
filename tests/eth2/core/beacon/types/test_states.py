import pytest

import ssz

from eth2.beacon.types.states import (
    BeaconState,
)

from eth2.beacon.tools.builder.initializer import (
    mock_validator,
)


def test_defaults(sample_beacon_state_params):
    state = BeaconState(**sample_beacon_state_params)
    assert state.validators == sample_beacon_state_params['validators']
    assert state.validators_update_epoch == sample_beacon_state_params['validators_update_epoch']  # noqa: E501
    assert ssz.encode(state)


def test_validators_and_balances_length(sample_beacon_state_params, config):
    # When len(BeaconState.validators) != len(BeaconState.validtor_balances)
    with pytest.raises(ValueError):
        BeaconState(**sample_beacon_state_params).copy(
            validators=tuple(
                mock_validator(pubkey, config)
                for pubkey in range(10)
            ),
        )


# TODO(ralexstokes) fix test
# @pytest.mark.parametrize(
#     'validator_index, new_pubkey, new_balance',
#     [
#         (0, 5566, 100),
#         (100, 5566, 100),
#     ]
# )
# def test_update_validator(genesis_state,
#                           validator_index,
#                           new_pubkey,
#                           new_balance, config):
#     state = genesis_state
#     validator = mock_validator(new_pubkey, config)

#     if validator_index < state.validator_count:
#         result_state = state.update_validator(
#             validator_index=validator_index,
#             validator=validator,
#             balance=new_balance,
#         )
#         assert result_state.balances[validator_index] == new_balance
#         assert result_state.validators[validator_index].pubkey == new_pubkey
#         assert state.validators[validator_index].pubkey != new_pubkey
#     else:
#         with pytest.raises(IndexError):
#             state.update_validator(
#                 validator_index=validator_index,
#                 validator=validator,
#                 balance=new_balance,
#             )
