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
    bls_setting: bool
    description: str
    pre: BeaconState
    post: BeaconState
    is_valid: bool = True


@dataclass
class StateTestCase(BaseTestCase):
    slots: Slot = Slot(0)
    blocks: Tuple[BeaconBlock, ...] = field(default_factory=tuple)
