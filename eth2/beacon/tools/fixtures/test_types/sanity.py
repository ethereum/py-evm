from typing import (
    Any,
    Dict,
    Optional,
    Sequence,
    Tuple,
)

from ssz.tools import (
    from_formatted_dict,
)

from eth_utils import (
    ValidationError,
)

from eth2.beacon.tools.fixtures.conditions import verify_state
from eth2.beacon.tools.fixtures.test_handler import TestHandler

from eth2.beacon.types.blocks import BeaconBlock
from eth2.beacon.types.states import BeaconState

from eth2.beacon.state_machines.forks.serenity.slot_processing import process_slots
from eth2.beacon.state_machines.forks.serenity.state_transitions import SerenityStateTransition

from eth2.configs import Eth2Config

from eth2.beacon.typing import Slot
from . import TestType


class BlocksHandler(TestHandler):
    name = "blocks"

    def parse_inputs(self,
                     test_case_data: Dict[str, Any]) -> Tuple[BeaconState, Tuple[BeaconBlock, ...]]:
        return (
            from_formatted_dict(
                test_case_data["pre"],
                BeaconState,
            ),
            tuple(
                from_formatted_dict(
                    block_data,
                    BeaconBlock,
                ) for block_data in test_case_data["blocks"]
            )
        )

    def parse_outputs(self, test_case_data: Dict[str, Any]) -> BeaconState:
        return from_formatted_dict(
            test_case_data["post"],
            BeaconState,
        )

    def valid(self, test_case_data: Dict[str, Any]) -> bool:
        return bool(test_case_data["post"])

    def run_with(self,
                 inputs: Tuple[BeaconState, Tuple[BeaconBlock]],
                 config: Eth2Config) -> BeaconState:
        state, blocks = inputs
        state_transition = SerenityStateTransition(config)
        for block in blocks:
            state = state_transition.apply_state_transition(
                state,
                block,
            )
            if block.state_root != state.hash_tree_root:
                raise ValidationError("block's state root did not match computed state root")
        return state

    def condition(self, output: BeaconState, expected_output: BeaconState) -> None:
        verify_state(output, expected_output)


class SlotsHandler(TestHandler):
    name = "slots"

    def parse_inputs(self, test_case_data: Dict[str, Any]) -> Tuple[BeaconState, int]:
        return (
            from_formatted_dict(
                test_case_data["pre"],
                BeaconState,
            ),
            test_case_data["slots"],
        )

    def parse_outputs(self, test_case_data: Dict[str, Any]) -> BeaconState:
        return from_formatted_dict(
            test_case_data["post"],
            BeaconState,
        )

    def run_with(self,
                 inputs: Tuple[BeaconState, Tuple[BeaconBlock]],
                 config: Eth2Config,
                 *auxillary: Sequence[Any]) -> BeaconState:
        state, offset = inputs
        target_slot = Slot(state.slot + offset)
        return process_slots(state, target_slot, config)

    def condition(self, output: BeaconState, expected_output: BeaconState) -> None:
        verify_state(output, expected_output)


class SanityTestType(TestType):
    name = "sanity"

    handlers = (
        BlocksHandler,
        SlotsHandler,
    )
