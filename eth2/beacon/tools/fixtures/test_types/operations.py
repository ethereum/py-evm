from pathlib import Path
from typing import (
    Any,
    Dict,
    Tuple,
)

from eth_utils import (
    ValidationError,
)

from ssz.tools import (
    from_formatted_dict,
)


from eth2.beacon.tools.fixtures.config_types import ConfigType
from eth2.beacon.tools.fixtures.conditions import verify_state
from eth2.beacon.tools.fixtures.test_handler import TestHandler
from eth2.beacon.state_machines.forks.serenity.block_processing import process_block_header
from eth2.beacon.types.blocks import BeaconBlock
from eth2.beacon.types.states import BeaconState
from eth2.configs import Eth2Config

from . import TestType


class BlockHeaderHandler(TestHandler):
    name = "block_header"

    def parse_inputs(self,
                     test_case_data: Dict[str, Any]) -> Tuple[BeaconState, BeaconBlock]:
        return (
            from_formatted_dict(
                test_case_data["pre"],
                BeaconState,
            ),
            from_formatted_dict(
                test_case_data["block"],
                BeaconBlock,
            ),
        )

    def parse_outputs(self, test_case_data: Dict[str, Any]) -> BeaconState:
        return from_formatted_dict(
            test_case_data["post"],
            BeaconState,
        )

    def valid(self, test_case_data: Dict[str, Any]) -> bool:
        return bool(test_case_data["post"])

    def run_with(self,
                 inputs: BeaconState,
                 config: Eth2Config) -> BeaconState:
        state, block = inputs
        check_proposer_signature = True
        try:
            return process_block_header(state, block, config, check_proposer_signature)
        # catch ValueError for bad signature
        except ValueError as e:
            raise ValidationError(e)

    def condition(self, output: BeaconState, expected_output: BeaconState) -> None:
        verify_state(output, expected_output)


class OperationsTestType(TestType):
    name = "operations"

    handlers = (
        BlockHeaderHandler,
    )

    @classmethod
    def build_path(cls,
                   tests_root_path: Path,
                   test_handler: TestHandler,
                   config_type: ConfigType) -> Path:
        file_name = f"{test_handler.name}_{config_type.name}.yaml"
        return tests_root_path / Path(cls.name) / Path(test_handler.name) / Path(file_name)
