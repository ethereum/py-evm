from typing import Type  # noqa: F401

from eth2.beacon.typing import (
    FromBlockParams,
)

from eth2.beacon.types.blocks import BaseBeaconBlock  # noqa: F401
from eth2.beacon.types.states import BeaconState  # noqa: F401

from eth2.beacon.state_machines.base import BeaconStateMachine
from eth2.beacon.state_machines.state_transitions import BaseStateTransition  # noqa: F401

from .configs import SERENITY_CONFIG
from .blocks import (
    create_serenity_block_from_parent,
    SerenityBeaconBlock,
)
from .states import SerenityBeaconState
from .state_transitions import SerenityStateTransition


class SerenityStateMachine(BeaconStateMachine):
    # fork name
    fork = 'serenity'  # type: str

    # classes
    block_class = SerenityBeaconBlock  # type: Type[BaseBeaconBlock]
    state_class = SerenityBeaconState  # type: Type[BeaconState]
    state_transition_class = SerenityStateTransition  # type: Type[BaseStateTransition]
    config = SERENITY_CONFIG

    # methods
    @staticmethod
    def create_block_from_parent(parent_block: BaseBeaconBlock,
                                 block_params: FromBlockParams) -> BaseBeaconBlock:
        return create_serenity_block_from_parent(parent_block, block_params)
