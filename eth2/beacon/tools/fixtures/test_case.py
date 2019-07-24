from typing import (
    Tuple,
)

from dataclasses import (
    dataclass,
    field,
)

from eth2.beacon.types.blocks import BeaconBlock
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import (
    Slot,
)


@dataclass
class BaseTestCase:
    line_number: int


@dataclass
class StateTestCase(BaseTestCase):
    bls_setting: bool
    description: str
    pre: BeaconState
    post: BeaconState
    slots: Slot = Slot(0)
    blocks: Tuple[BeaconBlock, ...] = field(default_factory=tuple)
    is_valid: bool = True
