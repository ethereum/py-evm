from typing import Any, Callable, Dict, Optional, Tuple, Type

from eth2.beacon.state_machines.forks.serenity.epoch_processing import (
    process_final_updates,
    process_justification_and_finalization,
    process_registry_updates,
    process_slashings,
)
from eth2.beacon.tools.fixtures.conditions import validate_state
from eth2.beacon.tools.fixtures.test_handler import TestHandler
from eth2.beacon.tools.fixtures.test_part import TestPart
from eth2.beacon.types.states import BeaconState
from eth2.configs import Eth2Config

from . import TestType


class EpochProcessingHandler(TestHandler[BeaconState, BeaconState]):
    processor: Callable[[BeaconState, Eth2Config], BeaconState]

    @classmethod
    def parse_inputs(
        _cls, test_case_parts: Dict[str, TestPart], metadata: Dict[str, Any]
    ) -> BeaconState:
        return test_case_parts["pre"].load(BeaconState)

    @staticmethod
    def parse_outputs(test_case_parts: Dict[str, TestPart]) -> BeaconState:
        return test_case_parts["post"].load(BeaconState)

    @classmethod
    def run_with(cls, inputs: BeaconState, config: Optional[Eth2Config]) -> BeaconState:
        state = inputs
        return cls.processor(state, config)

    @staticmethod
    def condition(output: BeaconState, expected_output: BeaconState) -> None:
        validate_state(output, expected_output)


class JustificationAndFinalizationHandler(EpochProcessingHandler):
    name = "justification_and_finalization"
    processor = process_justification_and_finalization


class RegistryUpdatesHandler(EpochProcessingHandler):
    name = "registry_updates"
    processor = process_registry_updates


class SlashingsHandler(EpochProcessingHandler):
    name = "slashings"
    processor = process_slashings


class FinalUpdatesHandler(EpochProcessingHandler):
    name = "final_updates"
    processor = process_final_updates


EpochProcessingHandlerType = Tuple[
    Type[JustificationAndFinalizationHandler],
    Type[RegistryUpdatesHandler],
    Type[SlashingsHandler],
    Type[FinalUpdatesHandler],
]


class EpochProcessingTestType(TestType[EpochProcessingHandlerType]):
    name = "epoch_processing"

    handlers = (
        JustificationAndFinalizationHandler,
        RegistryUpdatesHandler,
        SlashingsHandler,
        FinalUpdatesHandler,
    )
