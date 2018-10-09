from abc import (
    ABC,
)
import functools
import logging
from typing import (
    Iterable,
    Type,
)

from eth_typing import (
    Hash32
)
from eth_utils import (
    to_tuple,
)


from eth.constants import (
    GENESIS_PARENT_HASH,
)
from eth.exceptions import (
    BlockNotFound,
)
from eth.utils.datatypes import (
    Configurable,
)

from eth.beacon.db.chain import BaseBeaconChainDB
from eth.beacon.types.active_states import ActiveState
from eth.beacon.types.blocks import BaseBeaconBlock
from eth.beacon.types.crystallized_states import CrystallizedState
from eth.beacon.state_machines.configs import BeaconConfig  # noqa: F401


class BaseBeaconStateMachine(Configurable, ABC):
    fork = None  # type: str
    chaindb = None  # type: BaseBeaconChainDB
    config = None  # type: BeaconConfig

    block = None  # type: BaseBeaconBlock
    block_class = None  # type: Type[BaseBeaconBlock]

    crystallized_state_class = None  # type: Type[CrystallizedState]

    active_state_class = None  # type: Type[ActiveState]


class BeaconStateMachine(BaseBeaconStateMachine):
    """
    The :class:`~eth.beacon.state_machines.base.BeaconStateMachine` class represents
    the Chain rules for a specific protocol definition such as the Serenity network.
    """

    _crytallized_state = None  # type: CrystallizedState
    _active_state = None  # type: ActiveState

    def __init__(self, chaindb: BaseBeaconChainDB, block: BaseBeaconBlock) -> None:
        self.chaindb = chaindb
        self.block = self.get_block_class().from_block(block)

    #
    # Logging
    #
    @property
    def logger(self):
        return logging.getLogger('eth.beacon.state_machines.base.BeaconStateMachine.{0}'.format(
            self.__class__.__name__
        ))

    #
    # Block
    #
    @classmethod
    def get_block_class(cls) -> Type[BaseBeaconBlock]:
        """
        Return the :class:`~eth.beacon.types.blocks.BeaconBlock` class that this
        StateMachine uses for blocks.
        """
        if cls.block_class is None:
            raise AttributeError("No `block_class` has been set for this StateMachine")
        else:
            return cls.block_class

    @classmethod
    @functools.lru_cache(maxsize=32)
    @to_tuple
    def get_prev_blocks_to_slot(cls,
                                last_block_hash: Hash32,
                                chaindb: BaseBeaconChainDB,
                                depth: int,
                                start_slot: int) -> Iterable[BaseBeaconBlock]:
        if last_block_hash == GENESIS_PARENT_HASH:
            return

        block = chaindb.get_block_by_hash(last_block_hash)

        for _ in range(depth):
            yield block
            try:
                block = chaindb.get_block_by_hash(block.parent_hash)
            except (IndexError, BlockNotFound):
                break
            if block.slot_number < start_slot:
                break

    @property
    def parent_block(self) -> BaseBeaconBlock:
        return self.chaindb.get_block_by_hash(
            self.block.parent_hash
        )

    #
    # CrystallizedState
    #
    @property
    def crystallized_state(self) -> CrystallizedState:
        """
        Returns the latest CrystallizedState.
        """
        if self._crytallized_state is None:
            self._crytallized_state = self.chaindb.get_crystallized_state_by_root(
                self.parent_block.crystallized_state_root
            )
        return self._crytallized_state

    @classmethod
    def get_crystallized_state_class(cls) -> Type[CrystallizedState]:
        """
        Return the :class:`~eth.beacon.types.crystallized_states.CrystallizedState` class that this
        StateMachine uses for crystallized_state.
        """
        if cls.crystallized_state_class is None:
            raise AttributeError("No `crystallized_state_class` has been set for this StateMachine")
        else:
            return cls.crystallized_state_class

    #
    # ActiveState
    #
    @property
    def active_state(self) -> ActiveState:
        """
        Returns latest active state.

        It was backed up per cycle. The latest ActiveState could be reproduced by
        ``old_active_state`` and recent blocks.

        NOTE: The following logic in beacon chain spec will be changed with the current spec.
        """
        if self._active_state is None:
            # Reproduce ActiveState
            old_active_state_root = self.chaindb.get_active_state_root_by_crystallized(
                self.crystallized_state.hash
            )
            old_active_state = self.chaindb.get_active_state_by_root(old_active_state_root)
            old_active_state_slot = self.crystallized_state.last_state_recalc

            depth = self.config.CYCLE_LENGTH * 2
            blocks = self.get_prev_blocks_to_slot(
                self.parent_block.hash,
                self.chaindb,
                depth,
                start_slot=old_active_state_slot
            )
            blocks = blocks[::-1]

            self._active_state = self.get_active_state_class().from_old_active_state_and_blocks(
                old_active_state,
                blocks,
            )

        return self._active_state

    @classmethod
    def get_active_state_class(cls) -> Type[ActiveState]:
        """
        Return the :class:`~eth.beacon.types.active_states.ActiveState` class that this
        StateMachine uses for crystallized_state.
        """
        if cls.active_state_class is None:
            raise AttributeError("No `active_state_class` has been set for this StateMachine")
        else:
            return cls.active_state_class
