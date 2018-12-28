import pytest

from eth_utils import (
    denoms,
)

from eth.beacon.enums import (
    ValidatorStatusCode as code,
    ValidatorRegistryDeltaFlag,
)
from eth.beacon.helpers import (
    get_beacon_proposer_index,
)
from eth.beacon.types.shard_committees import ShardCommittee
from eth.beacon.types.validator_registry_delta_block import ValidatorRegistryDeltaBlock
from eth.beacon.validator_status_helpers import (
    activate_validator,
    exit_validator,
    get_new_persistent_committees,
    initiate_validator_exit,
    settle_penality_to_validator_and_whistleblower,
)


@pytest.mark.parametrize(
    (
        'default_validator_status,'
    ),
    [
        (code.PENDING_ACTIVATION)
    ]
)
def test_activate_validator(ten_validators_state,
                            default_validator_status):
    state = ten_validators_state
    index = 1
    result_state = activate_validator(
        state,
        index,
    )
    result_validator = result_state.validator_registry[index]

    new_validator_registry_delta_chain_tip = ValidatorRegistryDeltaBlock(
        latest_registry_delta_root=state.validator_registry_delta_chain_tip,
        validator_index=index,
        pubkey=result_validator.pubkey,
        flag=ValidatorRegistryDeltaFlag.ACTIVATION,
    ).root

    assert result_validator.status == code.ACTIVE
    assert result_validator.latest_status_change_slot == state.slot
    assert (
        result_state.validator_registry_delta_chain_tip == new_validator_registry_delta_chain_tip
    )
    # immutable
    assert state.validator_registry[index].status == code.PENDING_ACTIVATION


def test_initiate_validator_exit(ten_validators_state):
    state = ten_validators_state
    index = 1
    result_state = initiate_validator_exit(
        state,
        index,
    )
    result_validator = result_state.validator_registry[index]

    assert result_validator.status == code.ACTIVE_PENDING_EXIT
    assert result_validator.latest_status_change_slot == state.slot

    # immutable
    assert state.validator_registry[index].status == code.ACTIVE


@pytest.mark.parametrize(
    (
        'num_validators, committee,'
        'previous_status, new_status,'
        'expected_status'
    ),
    [
        (  # if previous_status == ValidatorStatusCode.EXITED_WITH_PENALTY: return state  # noqa: E501
            10,
            [4, 5, 6, 7],
            code.EXITED_WITH_PENALTY,
            code.EXITED_WITH_PENALTY,
            code.EXITED_WITH_PENALTY
        ),
        (  # if previous_status == ValidatorStatusCode.EXITED_WITH_PENALTY: return state  # noqa: E501
            10,
            [4, 5, 6, 7],
            code.EXITED_WITH_PENALTY,
            code.EXITED_WITHOUT_PENALTY,
            code.EXITED_WITH_PENALTY
        ),
        (  # new_status == expected_status
            10,
            [4, 5, 6, 7],
            code.ACTIVE_PENDING_EXIT,
            code.EXITED_WITHOUT_PENALTY,
            code.EXITED_WITHOUT_PENALTY
        ),
        # TODO: more test cases
    ],
)
def test_exit_validator(monkeypatch,
                        ten_validators_state,
                        previous_status,
                        new_status,
                        expected_status,
                        collective_penalty_calculation_period,
                        whistleblower_reward_quotient,
                        epoch_length,
                        max_deposit,
                        num_validators,
                        committee):
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

    validator_registry_exit_count = 2
    state_slot = 100
    state = ten_validators_state.copy(
        slot=state_slot,
        latest_penalized_exit_balances=(32 * denoms.gwei, ),
        validator_registry_exit_count=validator_registry_exit_count,
    )
    index = 1

    # Set previous_status
    validator = state.validator_registry[index].copy(
        status=previous_status,
    )
    state = state.update_validator_registry(
        validator_index=index,
        validator=validator,
    )

    result_state = exit_validator(
        state=state,
        index=index,
        new_status=new_status,
        collective_penalty_calculation_period=collective_penalty_calculation_period,
        whistleblower_reward_quotient=whistleblower_reward_quotient,
        epoch_length=epoch_length,
        max_deposit=max_deposit,
    )
    result_validator = result_state.validator_registry[index]
    assert result_validator.status == expected_status

    # immutable
    assert state.validator_registry[index].status == previous_status


def test_get_new_persistent_committees():
    persistent_committees = (
        (0, 1, 2),
        (3, 4, 5),
        (6, 7, 8),
    )

    new_persistent_committees = get_new_persistent_committees(
        persistent_committees,
        5,
    )

    assert new_persistent_committees[0] == persistent_committees[0]
    assert new_persistent_committees[1] == (3, 4)
    assert new_persistent_committees[2] == persistent_committees[2]


@pytest.mark.parametrize(
    (
        'num_validators, committee'
    ),
    [
        (10, [4, 5, 6, 7]),
    ],
)
def test_settle_penality_to_validator_and_whistleblower(monkeypatch,
                                                        num_validators,
                                                        committee,
                                                        ten_validators_state,
                                                        collective_penalty_calculation_period,
                                                        whistleblower_reward_quotient,
                                                        epoch_length,
                                                        max_deposit):
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

    state = ten_validators_state
    validator_index = 5
    state = settle_penality_to_validator_and_whistleblower(
        state=state,
        validator_index=validator_index,
        collective_penalty_calculation_period=collective_penalty_calculation_period,
        whistleblower_reward_quotient=whistleblower_reward_quotient,
        epoch_length=epoch_length,
        max_deposit=max_deposit,
    )

    latest_penalized_exit_balances_list = list(state.latest_penalized_exit_balances)
    last_penalized_slot = state.slot // collective_penalty_calculation_period
    latest_penalized_exit_balances_list[last_penalized_slot] = max_deposit
    latest_penalized_exit_balances = tuple(latest_penalized_exit_balances_list)
    whistleblower_reward = (
        state.validator_balances[validator_index] //
        whistleblower_reward_quotient
    )

    whistleblower_index = get_beacon_proposer_index(state, state.slot, epoch_length)

    assert (
        (
            state.validator_balances[validator_index] -
            state.validator_balances[whistleblower_index]
        ) == whistleblower_reward
    )
    assert state.latest_penalized_exit_balances == latest_penalized_exit_balances
