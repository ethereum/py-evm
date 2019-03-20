from abc import (
    ABC,
    abstractmethod,
)

from eth._utils.datatypes import (
    Configurable,
)

from eth2.configs import Eth2Config
from eth2.beacon.types.blocks import BaseBeaconBlock
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import Slot


class BaseStateTransition(Configurable, ABC):
    config = None

    def __init__(self, config: Eth2Config):
        self.config = config

    @abstractmethod
    def apply_state_transition(self,
                               state: BeaconState,
                               block: BaseBeaconBlock,
                               check_proposer_signature: bool=True) -> BeaconState:
        pass

    @abstractmethod
    def apply_state_transition_without_block(self,
                                             state: BeaconState,
                                             slot: Slot) -> BeaconState:
        """
        Advance the ``state`` to the beginning of the requested ``slot``.
        Return the resulting state at that slot assuming there are no
        intervening blocks. This method provides callers with some lookahead into
        the future state of the chain, useful for generating RANDAO reveals or
        computing future committee assignments.

        NOTE: Inserting blocks in intervening slots will invalidate the returned state.
        """
        pass

    @abstractmethod
    def cache_state(self,
                    state: BeaconState) -> BeaconState:
        pass

    @abstractmethod
    def per_slot_transition(self,
                            state: BeaconState) -> BeaconState:
        pass

    @abstractmethod
    def per_block_transition(self,
                             state: BeaconState,
                             block: BaseBeaconBlock,
                             check_proposer_signature: bool=True) -> BeaconState:
        pass

    @abstractmethod
    def per_epoch_transition(self, state: BeaconState) -> BeaconState:
        pass
