from typing import Type  # noqa: F401

from eth2.beacon.fork_choice.scoring import ScoringFn as ForkChoiceScoringFn
from eth2.beacon.fork_choice.lmd_ghost import (
    lmd_ghost_scoring,
)
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
    config = SERENITY_CONFIG

    # classes
    block_class = SerenityBeaconBlock  # type: Type[BaseBeaconBlock]
    state_class = SerenityBeaconState  # type: Type[BeaconState]
    state_transition_class = SerenityStateTransition  # type: Type[BaseStateTransition]

    # methods
    @staticmethod
    def create_block_from_parent(parent_block: BaseBeaconBlock,
                                 block_params: FromBlockParams) -> BaseBeaconBlock:
        return create_serenity_block_from_parent(parent_block, block_params)

    def _get_justified_head_state(self) -> BeaconState:
        justified_head = self.chaindb.get_justified_head(self.block_class)
        return self.chaindb.get_state_by_root(justified_head.state_root, self.state_class)

    def get_fork_choice_scoring(self) -> ForkChoiceScoringFn:
        state = self._get_justified_head_state()
        return lmd_ghost_scoring(
            self.chaindb,
            self.attestation_pool,
            state,
            self.config,
            self.block_class
        )
