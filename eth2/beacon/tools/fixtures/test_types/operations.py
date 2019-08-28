from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from eth_utils import ValidationError
import ssz
from ssz.tools import from_formatted_dict

from eth2._utils.bls import SignatureError
from eth2.beacon.state_machines.forks.serenity.block_processing import (
    process_block_header,
)
from eth2.beacon.state_machines.forks.serenity.operation_processing import (
    process_attestations,
    process_attester_slashings,
    process_deposits,
    process_proposer_slashings,
    process_transfers,
    process_voluntary_exits,
)
from eth2.beacon.tools.fixtures.conditions import validate_state
from eth2.beacon.tools.fixtures.config_types import ConfigType
from eth2.beacon.tools.fixtures.test_handler import TestHandler
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.attester_slashings import AttesterSlashing
from eth2.beacon.types.blocks import BeaconBlock, BeaconBlockBody
from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.proposer_slashings import ProposerSlashing
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.transfers import Transfer
from eth2.beacon.types.voluntary_exits import VoluntaryExit
from eth2.configs import Eth2Config

from . import TestType


class OperationHandler(TestHandler):
    name: str
    operation_name: Optional[str]
    operation_type: ssz.Serializable
    processor: Optional[Callable[[BeaconState, BeaconBlock, Eth2Config], BeaconState]]
    expected_exceptions: Tuple[Exception, ...] = ()

    def parse_inputs(self, test_case_data: Dict[str, Any]) -> Tuple[BeaconState, Any]:
        operation_name = (
            self.operation_name if hasattr(self, "operation_name") else self.name
        )
        return (
            from_formatted_dict(test_case_data["pre"], BeaconState),
            from_formatted_dict(test_case_data[operation_name], self.operation_type),
        )

    def parse_outputs(self, test_case_data: Dict[str, Any]) -> BeaconState:
        return from_formatted_dict(test_case_data["post"], BeaconState)

    def valid(self, test_case_data: Dict[str, Any]) -> bool:
        return bool(test_case_data["post"])

    def _update_config_if_needed(self, config: Eth2Config) -> Eth2Config:
        """
        Some ad-hoc work arounds...

        - Increase the count of allowed Transfer operations, even though we start with 0.
        """
        if self.name == "transfer":
            return config._replace(MAX_TRANSFERS=1)
        return config

    def run_with(self, inputs: BeaconState, config: Eth2Config) -> BeaconState:
        config = self._update_config_if_needed(config)
        state, operation = inputs
        # NOTE: we do not have an easy way to evaluate a single operation on the state
        # So, we wrap it in a beacon block. The following statement lets us rely on
        # the config given in a particular handler class while working w/in the
        # update API provided by `py-ssz`.
        block = BeaconBlock(body=BeaconBlockBody(**{f"{self.name}s": (operation,)}))
        try:
            return self.processor(state, block, config)
        except ValidationError as e:
            # if already a ValidationError, re-raise
            raise e
        except Exception as e:
            # check if the exception is expected...
            for exception in self.expected_exceptions:
                if isinstance(e, exception):
                    raise ValidationError(e)
            # else raise (and fail the pytest test case ...)
            raise e

    def condition(self, output: BeaconState, expected_output: BeaconState) -> None:
        validate_state(output, expected_output)


class AttestationHandler(OperationHandler):
    name = "attestation"
    operation_type = Attestation
    processor = staticmethod(process_attestations)
    expected_exceptions = (IndexError,)


class AttesterSlashingHandler(OperationHandler):
    name = "attester_slashing"
    operation_type = AttesterSlashing
    processor = staticmethod(process_attester_slashings)
    expected_exceptions = (SignatureError,)


class BlockHeaderHandler(OperationHandler):
    name = "block_header"
    operation_name = "block"
    operation_type = BeaconBlock

    def run_with(self, inputs: BeaconState, config: Eth2Config) -> BeaconState:
        state, block = inputs
        check_proposer_signature = True
        return process_block_header(state, block, config, check_proposer_signature)


class DepositHandler(OperationHandler):
    name = "deposit"
    operation_type = Deposit
    processor = staticmethod(process_deposits)


class ProposerSlashingHandler(OperationHandler):
    name = "proposer_slashing"
    operation_type = ProposerSlashing
    processor = staticmethod(process_proposer_slashings)
    expected_exceptions = (IndexError,)


class TransferHandler(OperationHandler):
    name = "transfer"
    operation_type = Transfer
    processor = staticmethod(process_transfers)
    expected_exceptions = (IndexError,)


class VoluntaryExitHandler(OperationHandler):
    name = "voluntary_exit"
    operation_type = VoluntaryExit
    processor = staticmethod(process_voluntary_exits)
    expected_exceptions = (IndexError,)


class OperationsTestType(TestType):
    name = "operations"

    handlers = (
        AttestationHandler,
        AttesterSlashingHandler,
        BlockHeaderHandler,
        DepositHandler,
        ProposerSlashingHandler,
        TransferHandler,
        VoluntaryExitHandler,
    )

    @classmethod
    def build_path(
        cls, tests_root_path: Path, test_handler: TestHandler, config_type: ConfigType
    ) -> Path:
        file_name = f"{test_handler.name}_{config_type.name}.yaml"
        return (
            tests_root_path / Path(cls.name) / Path(test_handler.name) / Path(file_name)
        )
