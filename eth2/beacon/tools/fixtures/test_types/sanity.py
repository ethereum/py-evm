from typing import Any, Dict, Optional, Tuple, Type

from eth_utils import ValidationError

from eth2.beacon.state_machines.forks.serenity.slot_processing import process_slots
from eth2.beacon.state_machines.forks.serenity.state_transitions import (
    SerenityStateTransition,
)
from eth2.beacon.tools.fixtures.conditions import validate_state
from eth2.beacon.tools.fixtures.test_handler import TestHandler
from eth2.beacon.tools.fixtures.test_part import TestPart
from eth2.beacon.types.blocks import BeaconBlock
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import Slot
from eth2.configs import Eth2Config

from . import TestType


class BlocksHandler(
    TestHandler[Tuple[BeaconState, Tuple[BeaconBlock, ...]], BeaconState]
):
    name = "blocks"

    @classmethod
    def parse_inputs(
        _cls, test_case_parts: Dict[str, TestPart], metadata: Dict[str, Any]
    ) -> Tuple[BeaconState, Tuple[BeaconBlock, ...]]:
        blocks_count = metadata["blocks_count"]
        return (
            test_case_parts["pre"].load(BeaconState),
            tuple(
                test_case_parts[f"blocks_{i}"].load(BeaconBlock)
                for i in range(blocks_count)
            ),
        )

    @staticmethod
    def parse_outputs(test_case_parts: Dict[str, TestPart]) -> BeaconState:
        return test_case_parts["post"].load(BeaconState)

    @staticmethod
    def valid(test_case_parts: Dict[str, TestPart]) -> bool:
        return bool(test_case_parts.get("post", None))

    @classmethod
    def run_with(
        _cls,
        inputs: Tuple[BeaconState, Tuple[BeaconBlock, ...]],
        config: Optional[Eth2Config],
    ) -> BeaconState:
        state, blocks = inputs
        state_transition = SerenityStateTransition(config)
        for block in blocks:
            state = state_transition.apply_state_transition(state, block)
            if block.state_root != state.hash_tree_root:
                raise ValidationError(
                    "block's state root did not match computed state root"
                )
        return state

    @staticmethod
    def condition(output: BeaconState, expected_output: BeaconState) -> None:
        validate_state(output, expected_output)


class SlotsHandler(TestHandler[Tuple[BeaconState, int], BeaconState]):
    name = "slots"

    @classmethod
    def parse_inputs(
        _cls, test_case_parts: Dict[str, TestPart], metadata: Dict[str, Any]
    ) -> Tuple[BeaconState, int]:
        return (
            test_case_parts["pre"].load(BeaconState),
            test_case_parts["slots"].load(),
        )

    @staticmethod
    def parse_outputs(test_case_parts: Dict[str, TestPart]) -> BeaconState:
        return test_case_parts["post"].load(BeaconState)

    @classmethod
    def run_with(
        _cls, inputs: Tuple[BeaconState, int], config: Optional[Eth2Config]
    ) -> BeaconState:
        state, offset = inputs
        target_slot = Slot(state.slot + offset)
        return process_slots(state, target_slot, config)

    @staticmethod
    def condition(output: BeaconState, expected_output: BeaconState) -> None:
        validate_state(output, expected_output)


SanityHandlerType = Tuple[Type[BlocksHandler], Type[SlotsHandler]]


class SanityTestType(TestType[SanityHandlerType]):
    name = "sanity"

    handlers = (BlocksHandler, SlotsHandler)
