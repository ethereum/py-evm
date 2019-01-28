from eth2._utils.tuple import (
    update_tuple_item,
)
from eth2.beacon.enums import (
    ValidatorRegistryDeltaFlag,
    ValidatorStatusFlags,
)
from eth2.beacon.helpers import (
    get_beacon_proposer_index,
    get_effective_balance,
)
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.validator_registry_delta_block import ValidatorRegistryDeltaBlock
from eth2.beacon.typing import (
    Ether,
    SlotNumber,
    ValidatorIndex,
)


#
# State update
#
def activate_validator(state: BeaconState,
                       index: ValidatorIndex,
                       genesis: bool,
                       genesis_slot: SlotNumber,
                       entry_exit_delay: int) -> BeaconState:
    """
    Activate the validator with the given ``index``.
    Return the updated state (immutable).
    """
    # Update validator.activation_slot
    validator = state.validator_registry[index]
    validator = validator.copy(
        activation_slot=genesis_slot if genesis else (state.slot + entry_exit_delay)
    )
    state = state.update_validator_registry(index, validator)

    # Update state.validator_registry_delta_chain_tip
    # TODO: use tree hashing
    new_validator_registry_delta_chain_tip = ValidatorRegistryDeltaBlock(
        latest_registry_delta_root=state.validator_registry_delta_chain_tip,
        validator_index=index,
        pubkey=validator.pubkey,
        slot=validator.activation_slot,
        flag=ValidatorRegistryDeltaFlag.ACTIVATION,
    ).root
    state = state.copy(
        validator_registry_delta_chain_tip=new_validator_registry_delta_chain_tip,
    )

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
                   entry_exit_delay: int) -> BeaconState:
    """
    Exit the validator with the given ``index``.
    Return the updated state (immutable).
    """
    validator = state.validator_registry[index]

    # The following updates only occur if not previous exited
    if validator.exit_slot <= state.slot + entry_exit_delay:
        return state

    # Update state.validator_registry_exit_count
    state = state.copy(
        validator_registry_exit_count=state.validator_registry_exit_count + 1,
    )

    # Update validator.exit_slot and exit_slot.exit_count
    validator = validator.copy(
        exit_slot=state.slot + entry_exit_delay,
        exit_count=state.validator_registry_exit_count,
    )
    state = state.update_validator_registry(index, validator)

    # Update state.validator_registry_delta_chain_tip
    # TODO: use tree hashing
    new_validator_registry_delta_chain_tip = ValidatorRegistryDeltaBlock(
        latest_registry_delta_root=state.validator_registry_delta_chain_tip,
        validator_index=index,
        pubkey=validator.pubkey,
        slot=validator.exit_slot,
        flag=ValidatorRegistryDeltaFlag.EXIT,
    ).root
    state = state.copy(
        validator_registry_delta_chain_tip=new_validator_registry_delta_chain_tip,
    )

    return state


def _settle_penality_to_validator_and_whistleblower(
        *,
        state: BeaconState,
        validator_index: ValidatorIndex,
        latest_penalized_exit_length: int,
        whistleblower_reward_quotient: int,
        epoch_length: int,
        max_deposit: Ether,
        target_committee_size: int,
        shard_count: int) -> BeaconState:
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
    validator.penalized_slot = state.slot
    """
    # Update `state.latest_penalized_balances`
    current_epoch_penalization_index = (state.slot // epoch_length) % latest_penalized_exit_length
    effective_balance = get_effective_balance(
        state.validator_balances,
        validator_index,
        max_deposit,
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
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )
    state = state.update_validator_balance(
        whistleblower_index,
        state.validator_balances[whistleblower_index] + whistleblower_reward,
    )

    # Update validator's balance and `penalized_slot` field
    validator = state.validator_registry[validator_index]
    validator = validator.copy(
        penalized_slot=state.slot,
    )
    state = state.update_validator(
        validator_index,
        validator,
        state.validator_balances[validator_index] - whistleblower_reward,
    )

    return state


def penalize_validator(state: BeaconState,
                       index: ValidatorIndex,
                       epoch_length: int,
                       latest_penalized_exit_length: int,
                       whistleblower_reward_quotient: int,
                       entry_exit_delay: int,
                       max_deposit: Ether,
                       target_committee_size: int,
                       shard_count: int) -> BeaconState:
    """
    Penalize the validator with the given ``index``.

    Exit the validator, penalize the validator, and reward the whistleblower.
    """
    state = exit_validator(state, index, entry_exit_delay)
    state = _settle_penality_to_validator_and_whistleblower(
        state=state,
        validator_index=index,
        latest_penalized_exit_length=latest_penalized_exit_length,
        whistleblower_reward_quotient=whistleblower_reward_quotient,
        epoch_length=epoch_length,
        max_deposit=max_deposit,
        target_committee_size=target_committee_size,
        shard_count=shard_count,
    )
    return state


def prepare_validator_for_withdrawal(state: BeaconState, index: ValidatorIndex) -> BeaconState:
    """
    Set the validator with the given ``index`` with ``WITHDRAWABLE`` flag.
    """
    validator = state.validator_registry[index]
    validator = validator.copy(
        status_flags=validator.status_flags | ValidatorStatusFlags.WITHDRAWABLE
    )
    state = state.update_validator_registry(index, validator)

    return state
