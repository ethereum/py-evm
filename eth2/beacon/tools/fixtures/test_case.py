from dataclasses import (
    dataclass,
)

from eth2.beacon.types.states import BeaconState


@dataclass
class BaseStateTestCase:
    line_number: int
    bls_setting: bool
    description: str
    pre: BeaconState
    post: BeaconState
    is_valid: bool = True
