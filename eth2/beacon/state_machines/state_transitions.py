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
                               block: BaseBeaconBlock=None,
                               future_slot: Slot=None,
                               check_proposer_signature: bool=True) -> BeaconState:
        """
        Applies the state transition function to ``state`` based on data in
        ``block`` or ``future_slot``. The ``block.slot`` or the ``future_slot``
        are used as a "target slot" to determine how the ``state`` should be
        advanced in the state transition.

        Invariant: ``state.slot`` is less than or equal to the "target slot".

        Callers are expected to provide exactly *one* of either ``block`` or ``future_slot``.
        ``block`` takes precedence over ``future_slot``. Perform a subsequent call to this
        method without the block if you need both functionalities.
        """
        pass
