from typing import Tuple, Union

from dataclasses import dataclass, field


from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.attester_slashings import AttesterSlashing
from eth2.beacon.types.blocks import BeaconBlock
from eth2.beacon.types.block_headers import BeaconBlockHeader
from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.proposer_slashings import ProposerSlashing
from eth2.beacon.types.transfers import Transfer
from eth2.beacon.types.voluntary_exits import VoluntaryExit


from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import Slot


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
