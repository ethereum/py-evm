from abc import (
    ABC,
    abstractmethod,
)

from eth_typing import (
    Hash32,
)
from eth._utils.datatypes import (
    Configurable,
)

from eth2.beacon.configs import BeaconConfig
from eth2.beacon.types.blocks import BaseBeaconBlock
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import Slot


class BaseStateTransition(Configurable, ABC):
    config = None

    def __init__(self, config: BeaconConfig):
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
                                             slot: Slot,
                                             parent_root: Hash32) -> BeaconState:
        """
        Advance the ``state`` to the beginning of the requested ``slot``.
        Return the resulting state at that slot assuming there are no
        intervening blocks. This method provides callers with some lookahead into
        the future state of the chain, useful for generating RANDAO reveals or
        computing future committee assignments.

        NOTE: Inserting blocks in intervening slots will (among other things) change the
        ``parent_root``, invalidating the returned state.
        """
        pass

    @abstractmethod
    def per_slot_transition(self,
                            state: BeaconState,
                            previous_block_root: Hash32) -> BeaconState:
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
