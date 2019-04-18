from eth2.configs import (
    Eth2Config,
)
from eth2.beacon.state_machines.state_transitions import BaseStateTransition
from eth2.beacon.types.blocks import BaseBeaconBlock
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import Slot

from .block_processing import (
    process_block_header,
    process_eth1_data,
    process_randao,
)
from .epoch_processing import (
    process_eth1_data_votes,
    process_justification,
    process_crosslinks,
    process_ejections,
    process_final_updates,
    process_rewards_and_penalties,
    process_validator_registry,
)
from .operation_processing import (
    process_attestations,
    process_attester_slashings,
    process_deposits,
    process_proposer_slashings,
    process_voluntary_exits,
)
from .slot_processing import (
    process_slot_transition,
    process_cache_state,
)


class SerenityStateTransition(BaseStateTransition):
    config = None

    def __init__(self, config: Eth2Config):
        self.config = config

    def apply_state_transition(self,
                               state: BeaconState,
                               block: BaseBeaconBlock,
                               check_proposer_signature: bool=True) -> BeaconState:
        if state.slot >= block.slot:
            return state

        for _ in range(state.slot, block.slot):
            state = self.cache_state(state)
            if (state.slot + 1) % self.config.SLOTS_PER_EPOCH == 0:
                state = self.per_epoch_transition(state)
            state = self.per_slot_transition(state)
            if state.slot == block.slot:
                state = self.per_block_transition(state, block, check_proposer_signature)
                break
        else:
            raise Exception(
                f"Invariant: state.slot ({state.slot}) should be less "
                f"than block.slot ({block.slot}) so that state transition terminates"
            )
        return state

    def apply_state_transition_without_block(self,
                                             state: BeaconState,
                                             slot: Slot) -> BeaconState:
        """
        Advance the ``state`` to the beginning of the requested ``slot``.
        Return the resulting state at that slot assuming there are no intervening blocks.
        See docs for :meth:`eth2.beacon.state_machines.state_transitions.BaseStateTransition.apply_state_transition_without_block`  # noqa: E501
        for more information about the behavior of this method.
        """
        if state.slot >= slot:
            return state

        for _ in range(state.slot, slot):
            state = self.cache_state(state)
            if (state.slot + 1) % self.config.SLOTS_PER_EPOCH == 0:
                state = self.per_epoch_transition(state)
            state = self.per_slot_transition(state)
            if state.slot == slot:
                break
        else:
            raise Exception(
                f"Invariant: state.slot ({state.slot}) should be less than slot ({slot}) "
                "so that state transition terminates"
            )
        return state

    def cache_state(self, state: BeaconState) -> BeaconState:
        return process_cache_state(state, self.config)

    def per_slot_transition(self, state: BeaconState) -> BeaconState:
        return process_slot_transition(state)

    def per_block_transition(self,
                             state: BeaconState,
                             block: BaseBeaconBlock,
                             check_proposer_signature: bool=True) -> BeaconState:
        state = process_block_header(state, block, self.config, check_proposer_signature)
        state = process_randao(state, block, self.config)
        state = process_eth1_data(state, block)

        # Operations
        state = process_proposer_slashings(state, block, self.config)
        state = process_attester_slashings(state, block, self.config)
        state = process_attestations(state, block, self.config)
        state = process_deposits(state, block, self.config)
        state = process_voluntary_exits(state, block, self.config)
        # TODO: state = process_transfers(state, block, self.config)

        return state

    def per_epoch_transition(self, state: BeaconState) -> BeaconState:
        state = process_eth1_data_votes(state, self.config)
        state = process_justification(state, self.config)
        state = process_crosslinks(state, self.config)
        state = process_rewards_and_penalties(state, self.config)
        state = process_ejections(state, self.config)
        state = process_validator_registry(state, self.config)
        state = process_final_updates(state, self.config)

        return state
