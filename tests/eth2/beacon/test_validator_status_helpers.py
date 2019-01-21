import pytest

from eth_utils import (
    ValidationError,
)

from eth2.beacon.constants import (
    FAR_FUTURE_SLOT,
    GWEI_PER_ETH,
)
from eth2.beacon.enums import (
    ValidatorRegistryDeltaFlag,
    ValidatorStatusFlags,
)
from eth2.beacon.helpers import (
    get_beacon_proposer_index,
)
from eth2.beacon.types.crosslink_committees import CrosslinkCommittee
from eth2.beacon.types.validator_registry_delta_block import ValidatorRegistryDeltaBlock
from eth2.beacon.validator_status_helpers import (
    _settle_penality_to_validator_and_whistleblower,
    activate_validator,
    exit_validator,
    initiate_validator_exit,
    prepare_validator_for_withdrawal,
    penalize_validator,
    update_tuple_item,
)


from tests.eth2.beacon.helpers import (
    mock_validator_record,
)


#
# Helper
#
@pytest.mark.parametrize(
    (
        'tuple_data, index, new_value, expected'
    ),
    [
        (
            (1, ) * 10,
            0,
            -99,
            (-99,) + (1, ) * 9,
        ),
        (
            (1, ) * 10,
            5,
            -99,
            (1, ) * 5 + (-99,) + (1, ) * 4,
        ),
        (
            (1, ) * 10,
            9,
            -99,
            (1, ) * 9 + (-99,),
        ),
        (
            (1, ) * 10,
            10,
            -99,
            ValidationError(),
        )
    ]
)
def test_update_tuple_item(tuple_data, index, new_value, expected):
    if isinstance(expected, Exception):
        with pytest.raises(ValidationError):
            update_tuple_item(
                tuple_data=tuple_data,
                index=index,
                new_value=new_value,
            )
    else:
        result = update_tuple_item(
            tuple_data=tuple_data,
            index=index,
            new_value=new_value,
        )
        assert result == expected


#
# State update
#
@pytest.mark.parametrize(
    (
        'genesis,'
    ),
    [
        (True),
        (False),
    ]
)
def test_activate_validator(genesis,
                            empty_beacon_state,
                            genesis_slot,
                            entry_exit_delay,
                            max_deposit):
    validator_count = 10
    state = empty_beacon_state.copy(
        validator_registry=tuple(
            mock_validator_record(
                pubkey=pubkey,
                is_active=False,
            )
            for pubkey in range(validator_count)
        ),
        validator_balances=(max_deposit * GWEI_PER_ETH,) * validator_count,
    )
    index = 1
    # Check that the `index`th validator in `state` is inactivated
    assert state.validator_registry[index].activation_slot == FAR_FUTURE_SLOT

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
    assert not (
        state.validator_registry[index].status_flags &
        ValidatorStatusFlags.INITIATED_EXIT
    )
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
    ),
    [
        (
            10,
            50,
            [4, 5, 6, 7],
            100,
            10,
            2,
        ),
        (
            10,
            10,
            [4, 5, 6, 7],
            100,
            110,
            2,
        ),
        (
            10,
            50,
            [4, 5, 6, 7],
            100,
            200,
            2,
        ),

    ],
)
def test_exit_validator(num_validators,
                        entry_exit_delay,
                        committee,
                        state_slot,
                        exit_slot,
                        validator_registry_exit_count,
                        ten_validators_state):
    # Unchanged
    state = ten_validators_state.copy(
        slot=state_slot,
        validator_registry_exit_count=validator_registry_exit_count,
    )
    index = 1

    # Set validator `exit_slot` prior to running `exit_validator`
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
    if validator.exit_slot <= state.slot + entry_exit_delay:
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

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              epoch_length):
        return (
            CrosslinkCommittee(
                shard=0,
                committee=committee,
                total_validator_count=num_validators,
            ),
        )

    monkeypatch.setattr(
        helpers,
        'get_crosslink_committees_at_slot',
        mock_get_crosslink_committees_at_slot
    )

    state = ten_validators_state
    validator_index = 5
    whistleblower_index = get_beacon_proposer_index(state, state.slot, epoch_length)
    effective_balance = max_deposit * GWEI_PER_ETH

    # Check the initial balance
    assert (
        state.validator_balances[validator_index] ==
        state.validator_balances[whistleblower_index] ==
        effective_balance
    )

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

    def mock_get_crosslink_committees_at_slot(state,
                                              slot,
                                              epoch_length):
        return (
            CrosslinkCommittee(
                shard=0,
                committee=committee,
                total_validator_count=num_validators,
            ),
        )

    monkeypatch.setattr(
        helpers,
        'get_crosslink_committees_at_slot',
        mock_get_crosslink_committees_at_slot
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
