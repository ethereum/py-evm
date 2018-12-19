from eth.beacon.types.blocks import BaseBeaconBlock
from eth.beacon.types.states import BeaconState

from eth.beacon.state_machines.configs import BeaconConfig
from eth.beacon.state_machines.state_transitions import BaseStateTransition

from .operations import (
    process_attestations,
)


class SerenityStateTransition(BaseStateTransition):
    config = None

    def __init__(self, config: BeaconConfig):
        self.config = config

    def apply_state_transition(self, state: BeaconState, block: BaseBeaconBlock) -> BeaconState:
        state = self.per_slot_transition(state, block)
        state = self.per_block_transition(state, block)
        state = self.per_epoch_transition(state, block)

        return state

    def per_slot_transition(self, state: BeaconState, block: BaseBeaconBlock) -> BeaconState:
        # TODO
        return state

    def per_block_transition(self, state: BeaconState, block: BaseBeaconBlock) -> BeaconState:
        # TODO
        state = process_attestations(state, block, self.config)
        return state

    def per_epoch_transition(self, state: BeaconState, block: BaseBeaconBlock) -> BeaconState:
        # TODO
        return state
