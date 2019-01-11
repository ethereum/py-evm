import pytest

from eth2.beacon.constants import (
    GWEI_PER_ETH,
)
from eth2.beacon.enums import (
    ValidatorRegistryDeltaFlag,
    ValidatorStatusFlags,
)
from eth2.beacon.helpers import (
    get_beacon_proposer_index,
)
from eth2.beacon.types.shard_committees import ShardCommittee
from eth2.beacon.types.validator_registry_delta_block import ValidatorRegistryDeltaBlock
from eth2.beacon.validator_status_helpers import (
    _settle_penality_to_validator_and_whistleblower,
    activate_validator,
    exit_validator,
    initiate_validator_exit,
    prepare_validator_for_withdrawal,
    penalize_validator,
)


@pytest.mark.parametrize(
    (
        'genesis,'
    ),
    [
        (True),
        (False),
    ]
)
def test_activate_validator(ten_validators_state, genesis, genesis_slot, entry_exit_delay):
    state = ten_validators_state
    index = 1
    result_state = activate_validator(
        state=state,
        index=index,
        genesis=genesis,
        genesis_slot=genesis_slot,
        entry_exit_delay=entry_exit_delay,
    )
    result_validator = result_state.validator_registry[index]

    new_validator_registry_delta_chain_tip = ValidatorRegistryDeltaBlock(
        latest_registry_delta_root=state.validator_registry_delta_chain_tip,
        validator_index=index,
        pubkey=result_validator.pubkey,
        slot=result_validator.activation_slot,
        flag=ValidatorRegistryDeltaFlag.ACTIVATION,
    ).root

    assert (
        result_state.validator_registry_delta_chain_tip == new_validator_registry_delta_chain_tip
    )
    if genesis:
        state.validator_registry[index].activation_slot == genesis_slot
    else:
        state.validator_registry[index].activation_slot == state.slot + entry_exit_delay


def test_initiate_validator_exit(ten_validators_state):
    state = ten_validators_state
    index = 1
    old_validator_status_flags = state.validator_registry[index].status_flags
    result_state = initiate_validator_exit(
        state,
        index,
    )

    assert result_state.validator_registry[index].status_flags == (
        old_validator_status_flags | ValidatorStatusFlags.INITIATED_EXIT
    )


@pytest.mark.parametrize(
    (
        'num_validators',
        'entry_exit_delay',
        'committee',
        'state_slot',
        'exit_slot',
        'validator_registry_exit_count',
        'not_previous_exited'
    ),
    [
        (
            10,
            50,
            [4, 5, 6, 7],
            100,
            10,
            0,
            True,
        ),
        (
            10,
            10,
            [4, 5, 6, 7],
            100,
            110,
            0,
            True,
        ),
        (
            10,
            50,
            [4, 5, 6, 7],
            100,
            200,
            0,
            False,
        ),

    ],
)
def test_exit_validator(num_validators,
                        entry_exit_delay,
                        committee,
                        state_slot,
                        exit_slot,
                        validator_registry_exit_count,
                        not_previous_exited,
                        ten_validators_state):
    # Unchanged

    validator_registry_exit_count = 2
    state_slot = 100
    state = ten_validators_state.copy(
        slot=state_slot,
        validator_registry_exit_count=validator_registry_exit_count,
    )
    index = 1

    # Set validator exit_slot
    validator = state.validator_registry[index].copy(
        exit_slot=exit_slot,
    )
    state = state.update_validator_registry(
        validator_index=index,
        validator=validator,
    )
    result_state = exit_validator(
        state=state,
        index=index,
        entry_exit_delay=entry_exit_delay,
    )
    if not_previous_exited:
        assert validator.exit_slot <= state.slot + entry_exit_delay
        assert state == result_state
        return
    else:
        assert validator.exit_slot > state.slot + entry_exit_delay
        result_validator = result_state.validator_registry[index]
        assert result_state.validator_registry_exit_count == validator_registry_exit_count + 1
        assert result_validator.exit_slot == state.slot + entry_exit_delay
        assert result_validator.exit_count == result_state.validator_registry_exit_count

        new_validator_registry_delta_chain_tip = ValidatorRegistryDeltaBlock(
            latest_registry_delta_root=state.validator_registry_delta_chain_tip,
            validator_index=index,
            pubkey=result_validator.pubkey,
            slot=result_validator.exit_slot,
            flag=ValidatorRegistryDeltaFlag.EXIT,
        ).root
        assert (
            result_state.validator_registry_delta_chain_tip ==
            new_validator_registry_delta_chain_tip
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
                                                        ten_validators_state,
                                                        latest_penalized_exit_length,
                                                        whistleblower_reward_quotient,
                                                        epoch_length,
                                                        max_deposit):
    from eth2.beacon import helpers

    def mock_get_shard_committees_at_slot(state,
                                          slot,
                                          epoch_length):
        return (
            ShardCommittee(
                shard=0,
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
    state = _settle_penality_to_validator_and_whistleblower(
        state=state,
        validator_index=validator_index,
        latest_penalized_exit_length=latest_penalized_exit_length,
        whistleblower_reward_quotient=whistleblower_reward_quotient,
        epoch_length=epoch_length,
        max_deposit=max_deposit,
    )

    # Check `state.latest_penalized_exit_balances`
    latest_penalized_exit_balances_list = list(state.latest_penalized_exit_balances)
    last_penalized_epoch = (state.slot // epoch_length) % latest_penalized_exit_length
    latest_penalized_exit_balances_list[last_penalized_epoch] = max_deposit * GWEI_PER_ETH
    latest_penalized_exit_balances = tuple(latest_penalized_exit_balances_list)

    assert state.latest_penalized_exit_balances == latest_penalized_exit_balances

    # Check penality and reward
    effective_balance = max_deposit * GWEI_PER_ETH
    whistleblower_reward = (
        effective_balance //
        whistleblower_reward_quotient
    )
    whistleblower_index = get_beacon_proposer_index(state, state.slot, epoch_length)

    assert (
        (
            state.validator_balances[whistleblower_index] -
            state.validator_balances[validator_index]
        ) == whistleblower_reward * 2
    )


@pytest.mark.parametrize(
    (
        'num_validators, committee'
    ),
    [
        (10, [4, 5, 6, 7]),
    ],
)
def test_penalize_validator(monkeypatch,
                            num_validators,
                            committee,
                            ten_validators_state,
                            epoch_length,
                            latest_penalized_exit_length,
                            whistleblower_reward_quotient,
                            entry_exit_delay,
                            max_deposit):
    from eth2.beacon import helpers

    def mock_get_shard_committees_at_slot(state,
                                          slot,
                                          epoch_length):
        return (
            ShardCommittee(
                shard=0,
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
    index = 1

    result_state = penalize_validator(
        state=state,
        index=index,
        epoch_length=epoch_length,
        latest_penalized_exit_length=latest_penalized_exit_length,
        whistleblower_reward_quotient=whistleblower_reward_quotient,
        entry_exit_delay=entry_exit_delay,
        max_deposit=max_deposit,
    )

    # Just check if `prepare_validator_for_withdrawal` applied these two functions
    expected_state = exit_validator(state, index, entry_exit_delay)
    expected_state = _settle_penality_to_validator_and_whistleblower(
        state=expected_state,
        validator_index=index,
        latest_penalized_exit_length=latest_penalized_exit_length,
        whistleblower_reward_quotient=whistleblower_reward_quotient,
        epoch_length=epoch_length,
        max_deposit=max_deposit,
    )

    assert result_state == expected_state


def test_prepare_validator_for_withdrawal(ten_validators_state):
    state = ten_validators_state
    index = 1
    old_validator_status_flags = state.validator_registry[index].status_flags
    result_state = prepare_validator_for_withdrawal(
        state,
        index,
    )

    assert result_state.validator_registry[index].status_flags == (
        old_validator_status_flags | ValidatorStatusFlags.WITHDRAWABLE
    )
