import pytest

from eth_utils import (
    denoms,
)

from eth.beacon.enums import ValidatorStatusCode as code

from eth.beacon.types.shard_committees import ShardCommittee

from eth.beacon.validator_status_helpers import (
    activate_validator,
    exit_validator,
    initiate_validator_exit,
)


@pytest.mark.parametrize(
    (
        'default_validator_status,'
    ),
    [
        (code.PENDING_ACTIVATION)
    ]
)
def test_activate_validator(ten_validators_state, default_validator_status):
    state = ten_validators_state
    index = 1
    result_state = activate_validator(
        state,
        index,
    )
    assert result_state.validator_registry[index].status == code.ACTIVE

    # immutable
    assert state.validator_registry[index].status == code.PENDING_ACTIVATION


def test_initiate_validator_exit(ten_validators_state):
    state = ten_validators_state
    index = 1
    result_state = initiate_validator_exit(
        state,
        index,
    )
    assert result_state.validator_registry[index].status == code.ACTIVE_PENDING_EXIT

    # immutable
    assert state.validator_registry[index].status == code.ACTIVE


@pytest.mark.parametrize(
    (
        'num_validators,committee'
    ),
    [
        (100, [4, 5, 6, 7]),
        # TODO: more test cases
    ],
)
def test_exit_validator(monkeypatch,
                        ten_validators_state,
                        collective_penalty_calculation_period,
                        whistleblower_reward_quotient,
                        epoch_length,
                        max_deposit,
                        num_validators,
                        committee,):
    from eth.beacon import helpers

    def mock_get_shard_committees_at_slot(state,
                                          slot,
                                          epoch_length):
        return (
            ShardCommittee(
                shard=1,
                committee=committee,
                total_validator_count=num_validators,
            ),
        )

    monkeypatch.setattr(
        helpers,
        'get_shard_committees_at_slot',
        mock_get_shard_committees_at_slot
    )

    state = ten_validators_state.copy(
        latest_penalized_exit_balances=(32 * denoms.gwei, )
    )
    index = 1
    result_state = exit_validator(
        state=state,
        index=index,
        new_status=code.EXITED_WITH_PENALTY,
        collective_penalty_calculation_period=collective_penalty_calculation_period,
        whistleblower_reward_quotient=whistleblower_reward_quotient,
        epoch_length=epoch_length,
        max_deposit=max_deposit,
    )
    assert result_state.validator_registry[index].status == code.EXITED_WITH_PENALTY

    # immutable
    assert state.validator_registry[index].status == code.ACTIVE
