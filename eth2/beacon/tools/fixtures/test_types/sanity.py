from typing import Any, Dict, Tuple, Type

from eth_utils import ValidationError
from ssz.tools import from_formatted_dict

from eth2.beacon.state_machines.forks.serenity.slot_processing import process_slots
from eth2.beacon.state_machines.forks.serenity.state_transitions import (
    SerenityStateTransition,
)
from eth2.beacon.tools.fixtures.conditions import validate_state
from eth2.beacon.tools.fixtures.test_handler import TestHandler
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
        _cls, test_case_data: Dict[str, Any]
    ) -> Tuple[BeaconState, Tuple[BeaconBlock, ...]]:
        return (
            from_formatted_dict(test_case_data["pre"], BeaconState),
            tuple(
                from_formatted_dict(block_data, BeaconBlock)
                for block_data in test_case_data["blocks"]
            ),
        )

    @staticmethod
    def parse_outputs(test_case_data: Dict[str, Any]) -> BeaconState:
        return from_formatted_dict(test_case_data["post"], BeaconState)

    @staticmethod
    def valid(test_case_data: Dict[str, Any]) -> bool:
        return bool(test_case_data["post"])

    @classmethod
    def run_with(
        _cls, inputs: Tuple[BeaconState, Tuple[BeaconBlock, ...]], config: Eth2Config
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
    def parse_inputs(_cls, test_case_data: Dict[str, Any]) -> Tuple[BeaconState, int]:
        return (
            from_formatted_dict(test_case_data["pre"], BeaconState),
            test_case_data["slots"],
        )

    @staticmethod
    def parse_outputs(test_case_data: Dict[str, Any]) -> BeaconState:
        return from_formatted_dict(test_case_data["post"], BeaconState)

    @classmethod
    def run_with(
        _cls, inputs: Tuple[BeaconState, int], config: Eth2Config
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
