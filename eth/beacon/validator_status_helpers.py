from typing import (
    Any,
    Iterable,
    Sequence,
)

from eth_utils import (
    to_tuple,
)
from eth_utils.toolz import (
    remove,
)

from eth.beacon.helpers import (
    get_beacon_proposer_index,
    get_effective_balance,
    get_new_validator_registry_delta_chain_tip,
)
from eth.beacon.types.states import BeaconState
from eth.beacon.types.validator_records import (
    ValidatorRecord,
    VALIDATOR_RECORD_EXITED_STATUSES,
)
from eth.beacon.enums import (
    ValidatorRegistryDeltaFlag,
)
from eth.beacon.enums import ValidatorStatusCode as code


#
# Helper for updating tuple item
#
def update_tuple_item(tuple_data: Sequence[Any], index: int, new_value: Any) -> Iterable[Any]:
    list_data = list(tuple_data)
    list_data[index] = new_value
    return tuple(list_data)


#
# State update
#
def update_validator_status(state: BeaconState,
                            index: int,
                            new_status: int,
                            collective_penalty_calculation_period: int,
                            whistleblower_reward_quotient: int,
                            epoch_length: int,
                            max_deposit: int) -> BeaconState:
    """
    Update the validator status with the given ``index`` to ``new_status``.
    Handle other general accounting related to this status update.
    Return the updated state (immutable).
    """
    if new_status == code.ACTIVE:
        state = activate_validator(state, index)
    if new_status == code.ACTIVE_PENDING_EXIT:
        state = initiate_validator_exit(state, index)
    if new_status in VALIDATOR_RECORD_EXITED_STATUSES:
        state = exit_validator(
            state,
            index,
            new_status,
            collective_penalty_calculation_period,
            whistleblower_reward_quotient,
            epoch_length,
            max_deposit,
        )

    return state


def activate_validator(state: BeaconState,
                       index: int) -> BeaconState:
    """
    Activate the validator with the given ``index``.
    Return the updated state (immutable).
    """
    validator = state.validator_registry[index]

    if validator.status != code.PENDING_ACTIVATION:
        return state

    validator = validator.copy(
        status=code.ACTIVE,
        latest_status_change_slot=state.slot,
    )
    state = state.update_validator_registry(index, validator)

    state = state.copy(
        validator_registry_delta_chain_tip=get_new_validator_registry_delta_chain_tip(
            current_validator_registry_delta_chain_tip=state.validator_registry_delta_chain_tip,
            validator_index=index,
            pubkey=validator.pubkey,
            flag=ValidatorRegistryDeltaFlag.ACTIVATION,
        ),
    )

    return state


def initiate_validator_exit(state: BeaconState,
                            index: int) -> BeaconState:
    """
    Initiate exit for the validator with the given ``index``.
    Return the updated state (immutable).
    """
    validator = state.validator_registry[index]

    if validator.status != code.ACTIVE:
        return state

    validator = validator.copy(
        status=code.ACTIVE_PENDING_EXIT,
        latest_status_change_slot=state.slot,
    )
    state = state.update_validator_registry(index, validator)

    return state


def exit_validator(state: BeaconState,
                   index: int,
                   new_status: int,
                   collective_penalty_calculation_period: int,
                   whistleblower_reward_quotient: int,
                   epoch_length: int,
                   max_deposit: int) -> BeaconState:
    """
    Exit the validator with the given ``index``.
    Return the updated state (immutable).
    """
    validator = state.validator_registry[index]
    prev_status = validator.status

    if prev_status == code.EXITED_WITH_PENALTY:
        # Case 1: EXITED_WITH_PENALTY -> EXITED_WITH_PENALTY
        # Case 2: EXITED_WITH_PENALTY -> EXITED_WITHOUT_PENALTY
        return state

    # Update validator's status and latest_status_change_slot
    validator = validator.copy(
        status=new_status,
        latest_status_change_slot=state.slot,
    )
    state = state.update_validator_registry(index, validator)

    # Calculate rewards and penalties
    if new_status == code.EXITED_WITH_PENALTY:
        # If new status is EXITED_WITH_PENALTY,
        # apply the penalty to the validator and the reward to whistleblower.
        state = settle_penality_to_validator_and_whistleblower(
            state=state,
            validator_index=index,
            validator=validator,
            collective_penalty_calculation_period=collective_penalty_calculation_period,
            whistleblower_reward_quotient=whistleblower_reward_quotient,
            epoch_length=epoch_length,
            max_deposit=max_deposit,
        )

    if prev_status == code.EXITED_WITHOUT_PENALTY:
        # Case 1: EXITED_WITHOUT_PENALTY -> EXITED_WITHOUT_PENALTY
        # Case 2: EXITED_WITHOUT_PENALTY -> EXITED_WITH_PENALTY
        return state
    else:
        # The following updates only occur if not previous exited
        # Update validator's exit_count
        validator = validator.copy(
            exit_count=state.validator_registry_exit_count,
        )
        state = state.update_validator_registry(index, validator)

        # Update the diff
        state = state.copy(
            validator_registry_exit_count=state.validator_registry_exit_count + 1,
            validator_registry_delta_chain_tip=get_new_validator_registry_delta_chain_tip(
                current_validator_registry_delta_chain_tip=state.validator_registry_delta_chain_tip,
                validator_index=index,
                pubkey=validator.pubkey,
                flag=ValidatorRegistryDeltaFlag.EXIT,
            ),
            # Remove validator from persistent_committees
            persistent_committees=get_new_persistent_committees(
                state.persistent_committees,
                index,
            ),
        )

    return state


@to_tuple
def get_new_persistent_committees(persistent_committees: Sequence[Sequence[int]],
                                  removing_validator_index: int) -> Iterable[Iterable[int]]:
    for committee in persistent_committees:
        def is_target(x: int) -> bool:
            return x == removing_validator_index

        yield remove(is_target, committee)


def settle_penality_to_validator_and_whistleblower(
        *,
        state: BeaconState,
        validator_index: int,
        validator: ValidatorRecord,
        collective_penalty_calculation_period: int,
        whistleblower_reward_quotient: int,
        epoch_length: int,
        max_deposit: int) -> BeaconState:
    last_penalized_slot = state.slot // collective_penalty_calculation_period
    latest_penalized_exit_balances = update_tuple_item(
        tuple_data=state.latest_penalized_exit_balances,
        index=last_penalized_slot,
        new_value=(
            state.latest_penalized_exit_balances[last_penalized_slot] +
            get_effective_balance(
                state.validator_balances,
                validator_index,
                max_deposit,
            )
        ),
    )
    state = state.copy(
        latest_penalized_exit_balances=latest_penalized_exit_balances,
    )

    # whistleblower
    whistleblower_reward = (
        state.validator_balances[validator_index] //
        whistleblower_reward_quotient
    )
    whistleblower_index = get_beacon_proposer_index(state, state.slot, epoch_length)
    state = state.update_validator_balance(
        whistleblower_index,
        state.validator_balances[whistleblower_index] - whistleblower_reward,
    )

    # validator
    state = state.update_validator_balance(
        validator_index,
        state.validator_balances[validator_index] - whistleblower_reward,
    )

    return state
