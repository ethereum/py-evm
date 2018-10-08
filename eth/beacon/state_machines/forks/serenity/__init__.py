
from typing import Type  # noqa: F401

from eth.beacon.types.active_states import ActiveState  # noqa: F401
from eth.beacon.types.blocks import BaseBeaconBlock  # noqa: F401
from eth.beacon.types.crystallized_states import CrystallizedState  # noqa: F401

from eth.beacon.state_machines.base import BeaconStateMachine

from .active_states import SerenityActiveState
from .blocks import SerenityBeaconBlock
from .crystallized_states import SerenityCrystallizedState
from .configs import SENERITY_CONFIG


class SerenityBeaconStateMachine(BeaconStateMachine):
    # fork name
    fork = 'serenity'  # type: str

    # classes
    block_class = SerenityBeaconBlock  # type: Type[BaseBeaconBlock]
    crystallized_state_class = SerenityCrystallizedState  # type: Type[CrystallizedState]
    active_state_class = SerenityActiveState  # type: Type[ActiveState]
    config = SENERITY_CONFIG
