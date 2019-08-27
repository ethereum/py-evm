from pathlib import Path
from typing import Any, Dict

from ssz.tools import from_formatted_dict

from eth2.beacon.state_machines.forks.serenity.epoch_processing import (
    process_crosslinks,
    process_final_updates,
    process_justification_and_finalization,
    process_registry_updates,
    process_slashings,
)
from eth2.beacon.tools.fixtures.conditions import verify_state
from eth2.beacon.tools.fixtures.config_types import ConfigType
from eth2.beacon.tools.fixtures.test_handler import TestHandler
from eth2.beacon.types.states import BeaconState
from eth2.configs import Eth2Config

from . import TestType


class EpochProcessingHandler(TestHandler):
    def parse_inputs(self, test_case_data: Dict[str, Any]) -> BeaconState:
        return from_formatted_dict(test_case_data["pre"], BeaconState)

    def parse_outputs(self, test_case_data: Dict[str, Any]) -> BeaconState:
        return from_formatted_dict(test_case_data["post"], BeaconState)

    def run_with(self, inputs: BeaconState, config: Eth2Config) -> BeaconState:
        state = inputs
        return self.__class__.processor(state, config)

    def condition(self, output: BeaconState, expected_output: BeaconState) -> None:
        verify_state(output, expected_output)


class JustificationAndFinalizationHandler(EpochProcessingHandler):
    name = "justification_and_finalization"
    processor = process_justification_and_finalization


class CrosslinksHandler(EpochProcessingHandler):
    name = "crosslinks"
    processor = process_crosslinks


class RegistryUpdatesHandler(EpochProcessingHandler):
    name = "registry_updates"
    processor = process_registry_updates


class SlashingsHandler(EpochProcessingHandler):
    name = "slashings"
    processor = process_slashings


class FinalUpdatesHandler(EpochProcessingHandler):
    name = "final_updates"
    processor = process_final_updates


class EpochProcessingTestType(TestType):
    name = "epoch_processing"

    handlers = (
        JustificationAndFinalizationHandler,
        CrosslinksHandler,
        RegistryUpdatesHandler,
        SlashingsHandler,
        FinalUpdatesHandler,
    )

    @classmethod
    def build_path(
        cls, tests_root_path: Path, test_handler: TestHandler, config_type: ConfigType
    ) -> Path:
        file_name = f"{test_handler.name}_{config_type.name}.yaml"
        return (
            tests_root_path / Path(cls.name) / Path(test_handler.name) / Path(file_name)
        )
