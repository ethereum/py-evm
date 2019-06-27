from eth_utils.toolz import (
    curry,
)

from eth2._utils.tuple import (
    update_tuple_item_with_fn,
)
from eth2.configs import (
    CommitteeConfig,
    Eth2Config,
)
from eth2.beacon.committee_helpers import (
    get_beacon_proposer_index,
)
from eth2.beacon.constants import FAR_FUTURE_EPOCH
from eth2.beacon.epoch_processing_helpers import (
    decrease_balance,
    get_churn_limit,
    get_delayed_activation_exit_epoch,
    increase_balance,
)
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.validators import Validator
from eth2.beacon.typing import (
    Epoch,
    ValidatorIndex,
)


def activate_validator(validator: Validator, activation_epoch: Epoch) -> Validator:
    return validator.copy(
        activation_eligibility_epoch=activation_epoch,
        activation_epoch=activation_epoch,
    )


def _compute_exit_queue_epoch(state: BeaconState, config: Eth2Config) -> int:
    slots_per_epoch = config.SLOTS_PER_EPOCH

    exit_epochs = tuple(
        v.exit_epoch for v in state.validators
        if v.exit_epoch != FAR_FUTURE_EPOCH
    )
    exit_queue_epoch = max(
        exit_epochs + (
            get_delayed_activation_exit_epoch(
                state.current_epoch(slots_per_epoch),
                config.ACTIVATION_EXIT_DELAY,
            ),
        )
    )
    exit_queue_churn = len(tuple(
        v for v in state.validators
        if v.exit_epoch == exit_queue_epoch
    ))
    if exit_queue_churn >= get_churn_limit(state, config):
        exit_queue_epoch += 1
    return exit_queue_epoch


def initiate_validator_exit_for_validator(state: BeaconState,
                                          config: Eth2Config,
                                          validator: Validator) -> Validator:
    """
    Performs the mutations to ``validator`` used to initiate an exit.
    More convenient given our immutability patterns compared to ``initiate_validator_exit``.
    """
    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        return validator

    exit_queue_epoch = _compute_exit_queue_epoch(state, config)

    validator.exit_epoch = exit_queue_epoch
    validator.withdrawable_epoch = validator.exit_epoch + config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY

    return validator


def initiate_validator_exit(state: BeaconState,
                            index: ValidatorIndex,
                            config: Eth2Config) -> BeaconState:
    """
    Initiate exit for the validator with the given ``index``.
    Return the updated state (immutable).
    """
    validator = state.validators[index]

    updated_validator = initiate_validator_exit_for_validator(
        state,
        config,
        validator,
    )

    return state.update_validator(index, updated_validator)


@curry
def _set_validator_slashed(withdrawable_epoch: Epoch,
                           v: Validator) -> Validator:
    return v.copy(
        slashed=True,
        withdrawable_epoch=withdrawable_epoch,
    )


def slash_validator(*,
                    state: BeaconState,
                    index: ValidatorIndex,
                    whistleblower_index: ValidatorIndex=None,
                    config: Eth2Config) -> BeaconState:
    """
    Slash the validator with index ``index``.

    Exit the validator, penalize the validator, and reward the whistleblower.
    """
    # NOTE: remove in phase 1
    assert whistleblower_index is None

    slots_per_epoch = config.SLOTS_PER_EPOCH

    current_epoch = state.current_epoch(slots_per_epoch)

    state = initiate_validator_exit(state, index, config)
    state = state.update_validator_with_fn(
        index,
        _set_validator_slashed(
            current_epoch + config.EPOCHS_PER_SLASHED_BALANCES_VECTOR,
        ),
    )

    slashed_balance = state.validators[index].effective_balance
    slashed_epoch = current_epoch % config.EPOCHS_PER_SLASHED_BALANCES_VECTOR
    state = state.copy(
        slashed_balances=update_tuple_item_with_fn(
            state.slashed_balances,
            slashed_epoch,
            sum,
            slashed_balance,
        )
    )

    proposer_index = get_beacon_proposer_index(state, CommitteeConfig(config))
    if whistleblower_index is None:
        whistleblower_index = proposer_index
    whistleblowing_reward = slashed_balance // config.WHISTLEBLOWING_REWARD_QUOTIENT
    proposer_reward = whistleblowing_reward // config.PROPOSER_REWARD_QUOTIENT
    state = increase_balance(state, proposer_index, proposer_reward)
    state = increase_balance(state, whistleblower_index, whistleblowing_reward - proposer_reward)
    state = decrease_balance(state, index, whistleblowing_reward)

    return state
