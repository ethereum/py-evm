from eth2.configs import (
    Eth2Config,
)
from eth2.beacon.state_machines.state_transitions import BaseStateTransition
from eth2.beacon.types.blocks import BaseBeaconBlock
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import Slot

from .block_processing import (
    process_block,
)
from .slot_processing import (
    process_slots,
)


class SerenityStateTransition(BaseStateTransition):
    config = None

    def __init__(self, config: Eth2Config):
        self.config = config

    def apply_state_transition(self,
                               state: BeaconState,
                               block: BaseBeaconBlock=None,
                               future_slot: Slot=None,
                               check_proposer_signature: bool=True) -> BeaconState:
        # NOTE: Callers should request a transition to some slot past the ``state.slot``.
        # This can be done by providing either a ``block`` *or* a ``future_slot``.
        # We enforce this invariant with the assertion on ``target_slot``.
        target_slot = block.slot if block else future_slot
        assert target_slot is not None

        state = process_slots(state, target_slot, self.config)

        if block:
            state = process_block(state, block, self.config, check_proposer_signature)

        return state
