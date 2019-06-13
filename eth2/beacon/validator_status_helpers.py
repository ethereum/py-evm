from eth_utils.toolz import (
    curry,
)

from eth2._utils.tuple import (
    update_tuple_item_with_fn,
)
from eth2.configs import (
    CommitteeConfig,
)
from eth2.beacon.committee_helpers import (
    get_beacon_proposer_index,
)
from eth2.beacon.constants import FAR_FUTURE_EPOCH
from eth2.beacon.epoch_processing_helpers import (
    decrease_balance,
    get_churn_limit,
    increase_balance,
)
from eth2.beacon.helpers import (
    get_delayed_activation_exit_epoch,
)
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.validators import Validator
from eth2.beacon.typing import (
    Epoch,
    Gwei,
    ValidatorIndex,
)


#
# State update
#
def activate_validator(validator: Validator, activation_epoch: Epoch) -> Validator:
    validator.activation_eligibility_epoch = activation_epoch
    validator.activation_epoch = activation_epoch
    return validator

# def activate_validator(state: BeaconState,
#                        index: ValidatorIndex,
#                        is_genesis: bool,
#                        genesis_epoch: Epoch,
#                        slots_per_epoch: int,
#                        activation_exit_delay: int) -> BeaconState:
#     """
#     Activate the validator with the given ``index``.
#     Return the updated state (immutable).
#     """
#     # Update validator.activation_epoch
#     validator = state.validator_registry[index].copy(
#         activation_epoch=genesis_epoch if is_genesis else get_delayed_activation_exit_epoch(
#             state.current_epoch(slots_per_epoch),
#             activation_exit_delay,
#         )
#     )
#     state = state.update_validator_registry(index, validator)

#     return state

def _compute_exit_queue_epoch(state: BeaconState,
                              slots_per_epoch: int,
                              min_per_epoch_churn_limit: int,
                              churn_limit_quotient: int) -> int:
    exit_epochs = tuple(
        v.exit_epoch for v in state.validator_registry
        if v.exit_epoch != FAR_FUTURE_EPOCH
    )
    exit_queue_epoch = max(
        exit_epochs + (
            get_delayed_activation_exit_epoch(
                state.current_epoch(slots_per_epoch)
            ),
        )
    )
    exit_queue_churn = len(tuple(
        v for v in state.validator_registry
        if v.exit_epoch == exit_queue_epoch
    ))
    if exit_queue_churn >= get_churn_limit(state,
                                           slots_per_epoch,
                                           min_per_epoch_churn_limit,
                                           churn_limit_quotient):
        exit_queue_epoch += 1
    return exit_queue_epoch


def initiate_validator_exit(state: BeaconState,
                            index: ValidatorIndex,
                            min_validator_withdrawability_delay: int) -> BeaconState:
    """
    Initiate exit for the validator with the given ``index``.
    Return the updated state (immutable).
    """
    validator = state.validator_registry[index]

    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        return state

    exit_queue_epoch = _compute_exit_queue_epoch(
        state,
    )

    validator.exit_epoch = exit_queue_epoch
    validator.withdrawable_epoch = validator.exit_epoch + min_validator_withdrawability_delay

    return state.update_validator_registry(index, validator)


# def exit_validator(state: BeaconState,
#                    index: ValidatorIndex,
#                    slots_per_epoch: int,
#                    activation_exit_delay: int) -> BeaconState:
#     """
#     Exit the validator with the given ``index``.
#     Return the updated state (immutable).
#     """
#     validator = state.validator_registry[index]

#     delayed_activation_exit_epoch = get_delayed_activation_exit_epoch(
#         state.current_epoch(slots_per_epoch),
#         activation_exit_delay,
#     )

#     # The following updates only occur if not previous exited
#     if validator.exit_epoch <= delayed_activation_exit_epoch:
#         return state

#     validator = validator.copy(
#         exit_epoch=delayed_activation_exit_epoch,
#     )
#     state = state.update_validator_registry(index, validator)

#     return state


# def _settle_penality_to_validator_and_whistleblower(
#         *,
#         state: BeaconState,
#         validator_index: ValidatorIndex,
#         latest_slashed_exit_length: int,
#         whistleblower_reward_quotient: int,
#         max_effective_balance: Gwei,
#         committee_config: CommitteeConfig) -> BeaconState:
#     """
#     Apply penality/reward to validator and whistleblower and update the meta data
#     """
#     slots_per_epoch = committee_config.SLOTS_PER_EPOCH

#     # Update `state.latest_slashed_balances`
#     current_epoch_penalization_index = state.current_epoch(
#         slots_per_epoch) % latest_slashed_exit_length
#     effective_balance = state.validator_registry[validator_index].effective_balance
#     slashed_exit_balance = (
#         state.latest_slashed_balances[current_epoch_penalization_index] +
#         effective_balance
#     )
#     latest_slashed_balances = update_tuple_item(
#         tuple_data=state.latest_slashed_balances,
#         index=current_epoch_penalization_index,
#         new_value=slashed_exit_balance,
#     )
#     state = state.copy(
#         latest_slashed_balances=latest_slashed_balances,
#     )

#     # Update whistleblower's balance
#     whistleblower_reward = (
#         effective_balance //
#         whistleblower_reward_quotient
#     )
#     whistleblower_index = get_beacon_proposer_index(
#         state,
#         state.slot,
#         committee_config,
#     )
#     state = state.update_validator_balance(
#         whistleblower_index,
#         state.validator_balances[whistleblower_index] + whistleblower_reward,
#     )

#     # Update validator's balance and `slashed`, `withdrawable_epoch` field
#     validator = state.validator_registry[validator_index].copy(
#         slashed=True,
#         withdrawable_epoch=state.current_epoch(slots_per_epoch) + latest_slashed_exit_length,
#     )
#     state = state.update_validator(
#         validator_index,
#         validator,
#         state.validator_balances[validator_index] - whistleblower_reward,
#     )

#     return state


@curry
def _set_validator_slashed(withdrawable_epoch: Epoch,
                           v: Validator) -> Validator:
    v.slashed = True
    v.withdrawable_epoch = withdrawable_epoch
    return v


def slash_validator(*,
                    state: BeaconState,
                    index: ValidatorIndex,
                    whistleblower_index: ValidatorIndex=None,
                    latest_slashed_exit_length: int,
                    whistleblower_reward_quotient: int,
                    proposer_reward_quotient: int,
                    max_effective_balance: Gwei,
                    min_validator_withdrawability_delay: int,
                    committee_config: CommitteeConfig) -> BeaconState:
    """
    Slash the validator with index ``index``.

    Exit the validator, penalize the validator, and reward the whistleblower.
    """
    slots_per_epoch = committee_config.SLOTS_PER_EPOCH

    current_epoch = state.current_epoch(slots_per_epoch)

    state = initiate_validator_exit(state, index, min_validator_withdrawability_delay)
    state = state.update_validator_registry_with_fn(
        index,
        _set_validator_slashed(
            current_epoch + latest_slashed_exit_length,
        ),
    )

    slashed_balance = state.validator_registry[index].effective_balance
    slashed_epoch = current_epoch % latest_slashed_exit_length
    state = state.copy(
        latest_slashed_balances=update_tuple_item_with_fn(
            state.latest_slashed_balances,
            slashed_epoch,
            sum,
            slashed_balance,
        )
    )

    proposer_index = get_beacon_proposer_index(state, committee_config)
    if whistleblower_index is None:
        whistleblower_index = proposer_index
    whistleblowing_reward = slashed_balance // whistleblower_reward_quotient
    proposer_reward = whistleblowing_reward // proposer_reward_quotient
    state = increase_balance(state, proposer_index, proposer_reward)
    state = increase_balance(state, whistleblower_index, whistleblowing_reward - proposer_reward)
    state = decrease_balance(state, index, whistleblowing_reward)

    return state


# def prepare_validator_for_withdrawal(state: BeaconState,
#                                      index: ValidatorIndex,
#                                      slots_per_epoch: int,
#                                      min_validator_withdrawability_delay: int) -> BeaconState:
#     """
#     Set the validator with the given ``index`` as withdrawable
#     ``MIN_VALIDATOR_WITHDRAWABILITY_DELAY`` after the current epoch.
#     """
#     validator = state.validator_registry[index].copy(
#         withdrawable_epoch=(
#             state.current_epoch(slots_per_epoch) + min_validator_withdrawability_delay
#         )
#     )
#     state = state.update_validator_registry(index, validator)

#     return state


#
# Validation
#
# def _validate_withdrawable_epoch(state_slot: Slot,
#                                  validator_withdrawable_epoch: Epoch,
#                                  slots_per_epoch: int) -> None:
#     if state_slot >= get_epoch_start_slot(validator_withdrawable_epoch, slots_per_epoch):
#         raise ValidationError(
#             f"state.slot ({state_slot}) should be less than "
#             f"validator.withdrawable_epoch ({validator_withdrawable_epoch})"
#         )
