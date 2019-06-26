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

from eth2.beacon.epoch_processing_helpers import (
    get_delayed_activation_exit_epoch,
)
from eth2.beacon.validator_status_helpers import (
    activate_validator,
    initiate_validator_exit,
    slash_validator,
)

from eth2.beacon.tools.builder.initializer import (
    mock_validator,
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
                            genesis_state,
                            genesis_epoch,
                            slots_per_epoch,
                            activation_exit_delay,
                            max_effective_balance,
                            config):
    validator_count = len(genesis_state.validators)
    state = genesis_state.copy(
        validators=tuple(
            mock_validator(
                pubkey=index.to_bytes(48, 'little'),
                config=config,
                is_active=False,
            )
            for index in range(validator_count)
        ),
    )
    index = 1
    # Check that the `index`th validator in `state` is inactivated
    assert state.validators[index].activation_epoch == FAR_FUTURE_EPOCH

    result_state = activate_validator(
        state=state,
        index=index,
        is_genesis=is_genesis,
        genesis_epoch=genesis_epoch,
        slots_per_epoch=slots_per_epoch,
        activation_exit_delay=activation_exit_delay,
    )

    if is_genesis:
        assert result_state.validators[index].activation_epoch == genesis_epoch
    else:
        assert (
            result_state.validators[index].activation_epoch ==
            get_delayed_activation_exit_epoch(
                state.current_epoch(slots_per_epoch),
                activation_exit_delay,
            )
        )


def test_initiate_validator_exit(genesis_state):
    state = genesis_state
    index = 1
    assert state.validators[index].initiated_exit is False

    result_state = initiate_validator_exit(
        state,
        index,
    )
    assert result_state.validators[index].initiated_exit is True


@pytest.mark.parametrize(
    (
        'validator_count',
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
def test_exit_validator(validator_count,
                        activation_exit_delay,
                        committee,
                        state_slot,
                        exit_epoch,
                        genesis_state,
                        slots_per_epoch):
    # Unchanged
    state = genesis_state.copy(
        slot=state_slot,
    )
    index = 1

    # Set validator `exit_epoch` prior to running `exit_validator`
    validator = state.validators[index].copy(
        exit_epoch=exit_epoch,
    )
    state = state.update_validators(
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
        result_validator = result_state.validators[index]
        assert result_validator.exit_epoch == get_delayed_activation_exit_epoch(
            state.current_epoch(slots_per_epoch),
            activation_exit_delay,
        )


@pytest.mark.parametrize(
    (
        'validator_count, committee'
    ),
    [
        (10, [4, 5, 6, 7]),
    ],
)
def test_settle_penality_to_validator_and_whistleblower(monkeypatch,
                                                        validator_count,
                                                        committee,
                                                        genesis_state,
                                                        epochs_per_slashed_balances_vector,
                                                        whistleblower_reward_quotient,
                                                        max_effective_balance,
                                                        committee_config):
    from eth2.beacon import committee_helpers

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              committee_config,
                                              registry_change=False):
        return (
            (committee, 1,),
        )

    monkeypatch.setattr(
        committee_helpers,
        'get_crosslink_committees_at_slot',
        mock_get_crosslink_committees_at_slot
    )

    state = genesis_state
    validator_index = 5
    whistleblower_index = get_beacon_proposer_index(
        state,
        state.slot,
        committee_config,
    )
    effective_balance = max_effective_balance

    # Check the initial balance
    assert (
        state.balances[validator_index] ==
        state.balances[whistleblower_index] ==
        effective_balance
    )

    state = _settle_penality_to_validator_and_whistleblower(
        state=state,
        validator_index=validator_index,
        epochs_per_slashed_balances_vector=epochs_per_slashed_balances_vector,
        whistleblower_reward_quotient=whistleblower_reward_quotient,
        max_effective_balance=max_effective_balance,
        committee_config=committee_config,
    )

    # Check `state.slashed_balances`
    slashed_balances_list = list(state.slashed_balances)
    last_slashed_epoch = (
        state.current_epoch(committee_config.SLOTS_PER_EPOCH) % epochs_per_slashed_balances_vector
    )
    slashed_balances_list[last_slashed_epoch] = max_effective_balance
    slashed_balances = tuple(slashed_balances_list)

    assert state.slashed_balances == slashed_balances

    # Check penality and reward
    whistleblower_reward = (
        effective_balance //
        whistleblower_reward_quotient
    )
    whistleblower_balance = state.balances[whistleblower_index]
    validator_balance = state.balances[validator_index]
    balance_difference = whistleblower_balance - validator_balance
    assert balance_difference == whistleblower_reward * 2


@pytest.mark.parametrize(
    (
        'validator_count, committee'
    ),
    [
        (10, [4, 5, 6, 7]),
    ],
)
def test_slash_validator(monkeypatch,
                         validator_count,
                         committee,
                         genesis_state,
                         genesis_epoch,
                         slots_per_epoch,
                         epochs_per_slashed_balances_vector,
                         whistleblower_reward_quotient,
                         activation_exit_delay,
                         max_effective_balance,
                         target_committee_size,
                         shard_count,
                         committee_config):
    from eth2.beacon import committee_helpers

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              committee_config,
                                              registry_change=False):
        return (
            (committee, 1,),
        )

    monkeypatch.setattr(
        committee_helpers,
        'get_crosslink_committees_at_slot',
        mock_get_crosslink_committees_at_slot
    )

    state = genesis_state
    index = 1

    result_state = slash_validator(
        state=state,
        index=index,
        epochs_per_slashed_balances_vector=epochs_per_slashed_balances_vector,
        whistleblower_reward_quotient=whistleblower_reward_quotient,
        max_effective_balance=max_effective_balance,
        committee_config=committee_config,
    )

    # Just check if `prepare_validator_for_withdrawal` applied these two functions
    expected_state = exit_validator(state, index, slots_per_epoch, activation_exit_delay)
    expected_state = _settle_penality_to_validator_and_whistleblower(
        state=expected_state,
        validator_index=index,
        epochs_per_slashed_balances_vector=epochs_per_slashed_balances_vector,
        whistleblower_reward_quotient=whistleblower_reward_quotient,
        max_effective_balance=max_effective_balance,
        committee_config=committee_config,
    )
    current_epoch = state.current_epoch(slots_per_epoch)
    validator = state.validators[index].copy(
        slashed=False,
        withdrawable_epoch=current_epoch + epochs_per_slashed_balances_vector,
    )
    expected_state.update_validators(index, validator)

    assert result_state == expected_state


def test_prepare_validator_for_withdrawal(genesis_state,
                                          slots_per_epoch,
                                          min_validator_withdrawability_delay):
    state = genesis_state
    index = 1
    result_state = prepare_validator_for_withdrawal(
        state,
        index,
        slots_per_epoch,
        min_validator_withdrawability_delay,
    )

    result_validator = result_state.validators[index]
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
