from abc import (
    ABC,
)
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

    # TODO: Add abstractmethods


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
    @to_tuple
    def get_prev_blocks(cls,
                        last_block_hash: Hash32,
                        chaindb: BaseBeaconChainDB,
                        max_search_depth: int,
                        min_slot_number: int) -> Iterable[BaseBeaconBlock]:
        """
        Return the previous blocks.

        Slot numbers are not guaranteed to be contiguous since it is possible for there
        to be no block at a given slot.  The search is bounded by two parameters.

        - `max_search_depth` - The maximum number of slots below the slot of the block denoted by
            `last_block_hash` that we should search.
        - `min_slot_number` - The slot number for which we should NOT include any deeper if reached.
        """
        if last_block_hash == GENESIS_PARENT_HASH:
            return

        block = chaindb.get_block_by_hash(last_block_hash)

        for _ in range(max_search_depth):
            yield block
            try:
                block = chaindb.get_block_by_hash(block.parent_hash)
            except (IndexError, BlockNotFound):
                break
            # Only include the blocks that are greater than or equal to min_slot_number.
            if block.slot_number < min_slot_number:
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
        Return the latest CrystallizedState.
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
        Return latest active state.

        It was backed up per cycle. The latest ActiveState could be reproduced by
        ``backup_active_state`` and recent blocks.
        """
        if self._active_state is None:
            # Reproduce ActiveState
            backup_active_state_root = self.chaindb.get_active_state_root_by_crystallized(
                self.crystallized_state.hash
            )
            backup_active_state = self.chaindb.get_active_state_by_root(backup_active_state_root)
            backup_active_state_slot = self.crystallized_state.last_state_recalc

            if backup_active_state_root == self.parent_block.active_state_root:
                # The backup ActiveState matches current block.
                self._active_state = backup_active_state
            else:
                # Get recent blocks after last ActiveState backup.
                max_search_depth = self.config.CYCLE_LENGTH * 2
                blocks = tuple(
                    reversed(
                        self.get_prev_blocks(
                            last_block_hash=self.parent_block.hash,
                            chaindb=self.chaindb,
                            max_search_depth=max_search_depth,
                            min_slot_number=backup_active_state_slot
                        )
                    )
                )

                self._active_state = self.get_active_state_class(
                ).from_backup_active_state_and_blocks(
                    backup_active_state,
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
