from eth_typing import (
    Hash32,
)

from eth.beacon.types.blocks import BaseBeaconBlock
from eth.beacon.types.states import BeaconState

from eth.beacon.state_machines.configs import BeaconConfig
from eth.beacon.state_machines.state_transitions import BaseStateTransition

from .operations import (
    process_attestations,
)
from .validation import (
    validate_serenity_proposer_signature,
)


class SerenityStateTransition(BaseStateTransition):
    config = None

    def __init__(self, config: BeaconConfig):
        self.config = config

    def apply_state_transition(self, state: BeaconState, block: BaseBeaconBlock) -> BeaconState:
        while state.slot != block.slot:
            state = self.per_slot_transition(state, block.parent_root)
            if state.slot == block.slot:
                state = self.per_block_transition(state, block)
            if state.slot % self.config.EPOCH_LENGTH == 0:
                state = self.per_epoch_transition(state)

        return state

    def per_slot_transition(self,
                            state: BeaconState,
                            previous_block_root: Hash32) -> BeaconState:
        # TODO
        state = state.copy(
            slot=state.slot + 1
        )
        return state

    def per_block_transition(self, state: BeaconState, block: BaseBeaconBlock) -> BeaconState:
        # TODO
        validate_serenity_proposer_signature(
            state,
            block,
            beacon_chain_shard_number=self.config.BEACON_CHAIN_SHARD_NUMBER,
            epoch_length=self.config.EPOCH_LENGTH,
        )

        state = process_attestations(state, block, self.config)

        return state

    def per_epoch_transition(self, state: BeaconState) -> BeaconState:
        # TODO
        return state
