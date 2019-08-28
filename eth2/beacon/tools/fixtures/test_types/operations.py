from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Type, Union

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
from eth2.beacon.tools.fixtures.test_handler import Input, Output, TestHandler
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

Operation = Union[
    ProposerSlashing, AttesterSlashing, Attestation, Deposit, VoluntaryExit, Transfer
]
OperationOrBlockHeader = Union[Operation, BeaconBlock]


class OperationHandler(
    TestHandler[Tuple[BeaconState, OperationOrBlockHeader], BeaconState]
):
    name: str
    operation_name: Optional[str]
    operation_type: ssz.Serializable
    processor: staticmethod  # Optional[Callable[[BeaconState, BeaconBlock, Eth2Config], BeaconState]]  # noqa: E501
    expected_exceptions: Tuple[Type[Exception], ...] = ()

    @classmethod
    def parse_inputs(cls, test_case_data: Dict[str, Any]) -> Tuple[BeaconState, Any]:
        operation_name = (
            cls.operation_name if hasattr(cls, "operation_name") else cls.name
        )
        return (
            from_formatted_dict(test_case_data["pre"], BeaconState),
            from_formatted_dict(test_case_data[operation_name], cls.operation_type),
        )

    @staticmethod
    def parse_outputs(test_case_data: Dict[str, Any]) -> BeaconState:
        return from_formatted_dict(test_case_data["post"], BeaconState)

    @staticmethod
    def valid(test_case_data: Dict[str, Any]) -> bool:
        return bool(test_case_data["post"])

    @classmethod
    def _update_config_if_needed(cls, config: Eth2Config) -> Eth2Config:
        """
        Some ad-hoc work arounds...

        - Increase the count of allowed Transfer operations, even though we start with 0.
        """
        if cls.name == "transfer":
            return config._replace(MAX_TRANSFERS=1)
        return config

    @classmethod
    def run_with(
        cls, inputs: Tuple[BeaconState, OperationOrBlockHeader], config: Eth2Config
    ) -> BeaconState:
        config = cls._update_config_if_needed(config)
        state, operation = inputs
        # NOTE: we do not have an easy way to evaluate a single operation on the state
        # So, we wrap it in a beacon block. The following statement lets us rely on
        # the config given in a particular handler class while working w/in the
        # update API provided by `py-ssz`.
        # NOTE: we ignore the type here, otherwise need to spell out each of the keyword
        # arguments individually... save some work and just build them dynamically
        block = BeaconBlock(
            body=BeaconBlockBody(**{f"{cls.name}s": (operation,)})  # type: ignore
        )
        try:
            return cls.processor(state, block, config)
        except ValidationError as e:
            # if already a ValidationError, re-raise
            raise e
        except Exception as e:
            # check if the exception is expected...
            for exception in cls.expected_exceptions:
                if isinstance(e, exception):
                    raise ValidationError(e)
            # else raise (and fail the pytest test case ...)
            raise e

    @staticmethod
    def condition(output: BeaconState, expected_output: BeaconState) -> None:
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

    @classmethod
    def run_with(
        _cls, inputs: Tuple[BeaconState, BeaconBlock], config: Eth2Config
    ) -> BeaconState:
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


OperationsHandlerType = Tuple[
    Type[AttestationHandler],
    Type[AttesterSlashingHandler],
    Type[BlockHeaderHandler],
    Type[DepositHandler],
    Type[ProposerSlashingHandler],
    Type[TransferHandler],
    Type[VoluntaryExitHandler],
]


class OperationsTestType(TestType[OperationsHandlerType]):
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
        cls,
        tests_root_path: Path,
        test_handler: TestHandler[Input, Output],
        config_type: ConfigType,
    ) -> Path:
        file_name = f"{test_handler.name}_{config_type.name}.yaml"
        return (
            tests_root_path / Path(cls.name) / Path(test_handler.name) / Path(file_name)
        )
