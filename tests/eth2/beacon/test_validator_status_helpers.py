import pytest

from eth_utils import (
    ValidationError,
)

from eth2.beacon.constants import (
    FAR_FUTURE_EPOCH,
)
from eth2.beacon.committee_helpers import (
    get_beacon_proposer_index,
)

from eth2.beacon.helpers import (
    get_delayed_activation_exit_epoch,
)
from eth2.beacon.validator_status_helpers import (
    _settle_penality_to_validator_and_whistleblower,
    _validate_withdrawable_epoch,
    activate_validator,
    exit_validator,
    initiate_validator_exit,
    prepare_validator_for_withdrawal,
    slash_validator,
)


from tests.eth2.beacon.helpers import (
    mock_validator_record,
)


#
# State update
#
@pytest.mark.parametrize(
    (
        'is_genesis,'
    ),
    [
        (True),
        (False),
    ]
)
def test_activate_validator(is_genesis,
                            filled_beacon_state,
                            genesis_epoch,
                            slots_per_epoch,
                            activation_exit_delay,
                            max_deposit_amount):
    validator_count = 10
    state = filled_beacon_state.copy(
        validator_registry=tuple(
            mock_validator_record(
                pubkey=index.to_bytes(48, 'big'),
                is_active=False,
            )
            for index in range(validator_count)
        ),
        validator_balances=(max_deposit_amount,) * validator_count,
    )
    index = 1
    # Check that the `index`th validator in `state` is inactivated
    assert state.validator_registry[index].activation_epoch == FAR_FUTURE_EPOCH

    result_state = activate_validator(
        state=state,
        index=index,
        is_genesis=is_genesis,
        genesis_epoch=genesis_epoch,
        slots_per_epoch=slots_per_epoch,
        activation_exit_delay=activation_exit_delay,
    )

    if is_genesis:
        assert result_state.validator_registry[index].activation_epoch == genesis_epoch
    else:
        assert (
            result_state.validator_registry[index].activation_epoch ==
            get_delayed_activation_exit_epoch(
                state.current_epoch(slots_per_epoch),
                activation_exit_delay,
            )
        )


def test_initiate_validator_exit(n_validators_state):
    state = n_validators_state
    index = 1
    assert state.validator_registry[index].initiated_exit is False

    result_state = initiate_validator_exit(
        state,
        index,
    )
    assert result_state.validator_registry[index].initiated_exit is True


@pytest.mark.parametrize(
    (
        'num_validators',
        'activation_exit_delay',
        'committee',
        'state_slot',
        'exit_epoch',
    ),
    [
        (
            10,
            50,
            [4, 5, 6, 7],
            100,
            10,
        ),
        (
            10,
            10,
            [4, 5, 6, 7],
            100,
            110,
        ),
        (
            10,
            50,
            [4, 5, 6, 7],
            100,
            200,
        ),
    ],
)
def test_exit_validator(num_validators,
                        activation_exit_delay,
                        committee,
                        state_slot,
                        exit_epoch,
                        n_validators_state,
                        slots_per_epoch):
    # Unchanged
    state = n_validators_state.copy(
        slot=state_slot,
    )
    index = 1

    # Set validator `exit_epoch` prior to running `exit_validator`
    validator = state.validator_registry[index].copy(
        exit_epoch=exit_epoch,
    )
    state = state.update_validator_registry(
        validator_index=index,
        validator=validator,
    )
    result_state = exit_validator(
        state=state,
        index=index,
        slots_per_epoch=slots_per_epoch,
        activation_exit_delay=activation_exit_delay,
    )
    if validator.exit_epoch <= state.current_epoch(slots_per_epoch) + activation_exit_delay:
        assert state == result_state
        return
    else:
        assert validator.exit_epoch > state.current_epoch(slots_per_epoch) + activation_exit_delay
        result_validator = result_state.validator_registry[index]
        assert result_validator.exit_epoch == get_delayed_activation_exit_epoch(
            state.current_epoch(slots_per_epoch),
            activation_exit_delay,
        )


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
                                                        n_validators_state,
                                                        latest_slashed_exit_length,
                                                        whistleblower_reward_quotient,
                                                        max_deposit_amount,
                                                        committee_config):
    from eth2.beacon import committee_helpers

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              committee_config):
        return (
            (committee, 1,),
        )

    monkeypatch.setattr(
        committee_helpers,
        'get_crosslink_committees_at_slot',
        mock_get_crosslink_committees_at_slot
    )

    state = n_validators_state
    validator_index = 5
    whistleblower_index = get_beacon_proposer_index(
        state,
        state.slot,
        committee_config,
    )
    effective_balance = max_deposit_amount

    # Check the initial balance
    assert (
        state.validator_balances[validator_index] ==
        state.validator_balances[whistleblower_index] ==
        effective_balance
    )

    state = _settle_penality_to_validator_and_whistleblower(
        state=state,
        validator_index=validator_index,
        latest_slashed_exit_length=latest_slashed_exit_length,
        whistleblower_reward_quotient=whistleblower_reward_quotient,
        max_deposit_amount=max_deposit_amount,
        committee_config=committee_config,
    )

    # Check `state.latest_slashed_balances`
    latest_slashed_balances_list = list(state.latest_slashed_balances)
    last_slashed_epoch = (
        state.current_epoch(committee_config.SLOTS_PER_EPOCH) % latest_slashed_exit_length
    )
    latest_slashed_balances_list[last_slashed_epoch] = max_deposit_amount
    latest_slashed_balances = tuple(latest_slashed_balances_list)

    assert state.latest_slashed_balances == latest_slashed_balances

    # Check penality and reward
    whistleblower_reward = (
        effective_balance //
        whistleblower_reward_quotient
    )
    whistleblower_balance = state.validator_balances[whistleblower_index]
    validator_balance = state.validator_balances[validator_index]
    balance_difference = whistleblower_balance - validator_balance
    assert balance_difference == whistleblower_reward * 2


@pytest.mark.parametrize(
    (
        'num_validators, committee'
    ),
    [
        (10, [4, 5, 6, 7]),
    ],
)
def test_slash_validator(monkeypatch,
                         num_validators,
                         committee,
                         n_validators_state,
                         genesis_epoch,
                         slots_per_epoch,
                         latest_slashed_exit_length,
                         whistleblower_reward_quotient,
                         activation_exit_delay,
                         max_deposit_amount,
                         target_committee_size,
                         shard_count,
                         committee_config):
    from eth2.beacon import committee_helpers

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              committee_config):
        return (
            (committee, 1,),
        )

    monkeypatch.setattr(
        committee_helpers,
        'get_crosslink_committees_at_slot',
        mock_get_crosslink_committees_at_slot
    )

    state = n_validators_state
    index = 1

    result_state = slash_validator(
        state=state,
        index=index,
        latest_slashed_exit_length=latest_slashed_exit_length,
        whistleblower_reward_quotient=whistleblower_reward_quotient,
        max_deposit_amount=max_deposit_amount,
        committee_config=committee_config,
    )

    # Just check if `prepare_validator_for_withdrawal` applied these two functions
    expected_state = exit_validator(state, index, slots_per_epoch, activation_exit_delay)
    expected_state = _settle_penality_to_validator_and_whistleblower(
        state=expected_state,
        validator_index=index,
        latest_slashed_exit_length=latest_slashed_exit_length,
        whistleblower_reward_quotient=whistleblower_reward_quotient,
        max_deposit_amount=max_deposit_amount,
        committee_config=committee_config,
    )
    current_epoch = state.current_epoch(slots_per_epoch)
    validator = state.validator_registry[index].copy(
        slashed=False,
        withdrawable_epoch=current_epoch + latest_slashed_exit_length,
    )
    expected_state.update_validator_registry(index, validator)

    assert result_state == expected_state


def test_prepare_validator_for_withdrawal(n_validators_state,
                                          slots_per_epoch,
                                          min_validator_withdrawability_delay):
    state = n_validators_state
    index = 1
    result_state = prepare_validator_for_withdrawal(
        state,
        index,
        slots_per_epoch,
        min_validator_withdrawability_delay,
    )

    result_validator = result_state.validator_registry[index]
    assert result_validator.withdrawable_epoch == (
        state.current_epoch(slots_per_epoch) + min_validator_withdrawability_delay
    )


@pytest.mark.parametrize(
    (
        'slots_per_epoch',
        'state_slot',
        'validate_withdrawable_epoch',
        'success'
    ),
    [
        (4, 8, 1, False),
        (4, 8, 2, False),
        (4, 7, 2, True),
        (4, 8, 3, True),
    ]
)
def test_validate_withdrawable_epoch(slots_per_epoch,
                                     state_slot,
                                     validate_withdrawable_epoch,
                                     success):
    if success:
        _validate_withdrawable_epoch(state_slot, validate_withdrawable_epoch, slots_per_epoch)
    else:
        with pytest.raises(ValidationError):
            _validate_withdrawable_epoch(state_slot, validate_withdrawable_epoch, slots_per_epoch)
