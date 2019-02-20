from eth_utils import (
    ValidationError,
)

from eth2._utils.tuple import (
    update_tuple_item,
)
from eth2.beacon.committee_helpers import (
    get_beacon_proposer_index,
)
from eth2.beacon.configs import (
    CommitteeConfig,
)
from eth2.beacon.enums import (
    ValidatorStatusFlags,
)
from eth2.beacon.helpers import (
    get_entry_exit_effect_epoch,
    get_effective_balance,
    get_epoch_start_slot,
)
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import (
    EpochNumber,
    Gwei,
    SlotNumber,
    ValidatorIndex,
)


#
# State update
#
def activate_validator(state: BeaconState,
                       index: ValidatorIndex,
                       is_genesis: bool,
                       genesis_epoch: EpochNumber,
                       epoch_length: int,
                       entry_exit_delay: int) -> BeaconState:
    """
    Activate the validator with the given ``index``.
    Return the updated state (immutable).
    """
    # Update validator.activation_epoch
    validator = state.validator_registry[index].copy(
        activation_epoch=genesis_epoch if is_genesis else get_entry_exit_effect_epoch(
            state.current_epoch(epoch_length),
            entry_exit_delay,
        )
    )
    state = state.update_validator_registry(index, validator)

    return state


def initiate_validator_exit(state: BeaconState,
                            index: ValidatorIndex) -> BeaconState:
    """
    Initiate exit for the validator with the given ``index``.
    Return the updated state (immutable).
    """
    validator = state.validator_registry[index]
    validator = validator.copy(
        status_flags=validator.status_flags | ValidatorStatusFlags.INITIATED_EXIT
    )
    state = state.update_validator_registry(index, validator)

    return state


def exit_validator(state: BeaconState,
                   index: ValidatorIndex,
                   epoch_length: int,
                   entry_exit_delay: int) -> BeaconState:
    """
    Exit the validator with the given ``index``.
    Return the updated state (immutable).
    """
    validator = state.validator_registry[index]

    entry_exit_effect_epoch = get_entry_exit_effect_epoch(
        state.current_epoch(epoch_length),
        entry_exit_delay,
    )

    # The following updates only occur if not previous exited
    if validator.exit_epoch <= entry_exit_effect_epoch:
        return state

    validator = validator.copy(
        exit_epoch=state.current_epoch(epoch_length) + entry_exit_delay,
    )
    state = state.update_validator_registry(index, validator)

    return state


def _settle_penality_to_validator_and_whistleblower(
        *,
        state: BeaconState,
        validator_index: ValidatorIndex,
        latest_penalized_exit_length: int,
        whistleblower_reward_quotient: int,
        max_deposit_amount: Gwei,
        committee_config: CommitteeConfig) -> BeaconState:
    """
    Apply penality/reward to validator and whistleblower and update the meta data

    More intuitive pseudo-code:
    current_epoch_penalization_index = (state.slot // EPOCH_LENGTH) % LATEST_PENALIZED_EXIT_LENGTH
    state.latest_penalized_balances[current_epoch_penalization_index] += (
        get_effective_balance(state, index)
    )
    whistleblower_index = get_beacon_proposer_index(state, state.slot)
    whistleblower_reward = get_effective_balance(state, index) // WHISTLEBLOWER_REWARD_QUOTIENT
    state.validator_balances[whistleblower_index] += whistleblower_reward
    state.validator_balances[index] -= whistleblower_reward
    validator.slashed_epoch = slot_to_epoch(state.slot)
    """
    epoch_length = committee_config.EPOCH_LENGTH

    # Update `state.latest_penalized_balances`
    current_epoch_penalization_index = state.current_epoch(
        epoch_length) % latest_penalized_exit_length
    effective_balance = get_effective_balance(
        state.validator_balances,
        validator_index,
        max_deposit_amount,
    )
    penalized_exit_balance = (
        state.latest_penalized_balances[current_epoch_penalization_index] +
        effective_balance
    )
    latest_penalized_balances = update_tuple_item(
        tuple_data=state.latest_penalized_balances,
        index=current_epoch_penalization_index,
        new_value=penalized_exit_balance,
    )
    state = state.copy(
        latest_penalized_balances=latest_penalized_balances,
    )

    # Update whistleblower's balance
    whistleblower_reward = (
        effective_balance //
        whistleblower_reward_quotient
    )
    whistleblower_index = get_beacon_proposer_index(
        state,
        state.slot,
        committee_config,
    )
    state = state.update_validator_balance(
        whistleblower_index,
        state.validator_balances[whistleblower_index] + whistleblower_reward,
    )

    # Update validator's balance and `slashed_epoch` field
    validator = state.validator_registry[validator_index]
    validator = validator.copy(
        slashed_epoch=state.current_epoch(epoch_length),
    )
    state = state.update_validator(
        validator_index,
        validator,
        state.validator_balances[validator_index] - whistleblower_reward,
    )

    return state


def slash_validator(*,
                    state: BeaconState,
                    index: ValidatorIndex,
                    latest_penalized_exit_length: int,
                    whistleblower_reward_quotient: int,
                    max_deposit_amount: Gwei,
                    committee_config: CommitteeConfig) -> BeaconState:
    """
    Slash the validator with index ``index``.

    Exit the validator, penalize the validator, and reward the whistleblower.
    """
    epoch_length = committee_config.EPOCH_LENGTH
    entry_exit_delay = committee_config.ENTRY_EXIT_DELAY

    validator = state.validator_registry[index]

    # [TO BE REMOVED IN PHASE 2]
    _validate_withdrawal_epoch(state.slot, validator.withdrawal_epoch, epoch_length)

    state = exit_validator(state, index, epoch_length, entry_exit_delay)
    state = _settle_penality_to_validator_and_whistleblower(
        state=state,
        validator_index=index,
        latest_penalized_exit_length=latest_penalized_exit_length,
        whistleblower_reward_quotient=whistleblower_reward_quotient,
        max_deposit_amount=max_deposit_amount,
        committee_config=committee_config,
    )

    # Update validator
    current_epoch = state.current_epoch(epoch_length)
    validator = validator.copy(
        slashed_epoch=current_epoch,
        withdrawal_epoch=current_epoch + latest_penalized_exit_length,
    )
    state.update_validator_registry(index, validator)

    return state


def prepare_validator_for_withdrawal(state: BeaconState,
                                     index: ValidatorIndex,
                                     epoch_length: int,
                                     min_validator_withdrawability_delay: int) -> BeaconState:
    """
    Set the validator with the given ``index`` with ``WITHDRAWABLE`` flag.
    """
    validator = state.validator_registry[index]
    validator = validator.copy(
        status_flags=validator.status_flags | ValidatorStatusFlags.WITHDRAWABLE,
        withdrawal_epoch=state.current_epoch(epoch_length) + min_validator_withdrawability_delay
    )
    state = state.update_validator_registry(index, validator)

    return state


#
# Validation
#
def _validate_withdrawal_epoch(state_slot: SlotNumber,
                               validator_withdrawal_epoch: EpochNumber,
                               epoch_length: int) -> None:
    # TODO: change to `validate_withdrawable_epoch`
    if state_slot >= get_epoch_start_slot(validator_withdrawal_epoch, epoch_length):
        raise ValidationError(
            f"state.slot ({state_slot}) should be less than "
            f"validator.withdrawal_epoch ({validator_withdrawal_epoch})"
        )
