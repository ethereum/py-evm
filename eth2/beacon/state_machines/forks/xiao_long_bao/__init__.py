from typing import (  # noqa: F401,
    Type
)

from eth2.beacon.state_machines.base import (
    BeaconStateMachine,
)
from eth2.beacon.state_machines.forks.serenity.blocks import (
    SerenityBeaconBlock,
    create_serenity_block_from_parent,
)
from eth2.beacon.state_machines.forks.serenity.state_transitions import (
    SerenityStateTransition,
)
from eth2.beacon.state_machines.forks.serenity.states import (
    SerenityBeaconState,
)
from eth2.beacon.state_machines.state_transitions import (  # noqa: F401,
    BaseStateTransition,
)
from eth2.beacon.types.blocks import (  # noqa: F401,
    BaseBeaconBlock,
)
from eth2.beacon.types.states import (  # noqa: F401,
    BeaconState,
)
from eth2.beacon.typing import (
    FromBlockParams,
)

from .configs import (
    XIAO_LONG_BAO_CONFIG,
)


class XiaoLongBaoStateMachine(BeaconStateMachine):
    # fork name
    fork = 'xiao_long_bao'  # type: str

    # classes
    block_class = SerenityBeaconBlock  # type: Type[BaseBeaconBlock]
    state_class = SerenityBeaconState  # type: Type[BeaconState]
    state_transition_class = SerenityStateTransition  # type: Type[BaseStateTransition]
    config = XIAO_LONG_BAO_CONFIG

    # methods
    @staticmethod
    def create_block_from_parent(parent_block: BaseBeaconBlock,
                                 block_params: FromBlockParams) -> BaseBeaconBlock:
        return create_serenity_block_from_parent(parent_block, block_params)
