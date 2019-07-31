from dataclasses import dataclass, field
from typing import Any, Dict, Sequence, Tuple, Union

from eth2._utils.bls import bls
from eth2._utils.bls.backends import PyECCBackend
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.attester_slashings import AttesterSlashing
from eth2.beacon.types.block_headers import BeaconBlockHeader
from eth2.beacon.types.blocks import BeaconBlock
from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.proposer_slashings import ProposerSlashing
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.transfers import Transfer
from eth2.beacon.types.voluntary_exits import VoluntaryExit
from eth2.beacon.typing import Slot
from eth2.configs import Eth2Config

from .test_handler import TestHandler


def _select_bls_backend(bls_setting: int) -> None:
    if bls_setting == 2:
        bls.use_noop_backend()
    elif bls_setting == 1:
        bls.use(PyECCBackend)
    else:  # do not verify BLS to save time
        bls.use_noop_backend()


Operation = Union[
    ProposerSlashing, AttesterSlashing, Attestation, Deposit, VoluntaryExit, Transfer
]
OperationOrBlockHeader = Union[Operation, BeaconBlockHeader]


@dataclass
class BaseTestCase:
    handler: str
    index: int


@dataclass
class StateTestCase(BaseTestCase):
    bls_setting: bool
    description: str
    pre: BeaconState
    post: BeaconState
    slots: Slot = Slot(0)
    blocks: Tuple[BeaconBlock, ...] = field(default_factory=tuple)
    is_valid: bool = True


@dataclass
class OperationCase(BaseTestCase):
    bls_setting: bool
    description: str
    pre: BeaconState
    operation: OperationOrBlockHeader
    post: BeaconState
    is_valid: bool = True


class TestCase:
    def __init__(
        self,
        index: int,
        test_case_data: Dict[str, Any],
        handler: TestHandler,
        config: Eth2Config,
    ) -> None:
        self.index = index
        self.description = test_case_data.get("description", "")
        self.bls_setting = test_case_data.get("bls_setting", 0)
        self.config = config
        self.test_case_data = test_case_data
        self.handler = handler

    def valid(self) -> bool:
        return self.handler.valid(self.test_case_data)

    def execute(self, *auxillary: Sequence[Any]) -> None:
        _select_bls_backend(self.bls_setting)
        inputs = self.handler.parse_inputs(self.test_case_data)
        outputs = self.handler.run_with(inputs, self.config, *auxillary)
        expected_outputs = self.handler.parse_outputs(self.test_case_data)
        self.handler.condition(outputs, expected_outputs)
