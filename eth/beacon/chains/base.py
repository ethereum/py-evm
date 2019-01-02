from __future__ import absolute_import

from abc import (
    ABC,
    abstractmethod
)
from typing import (
    Any,
    Tuple,
    Type,
)

import logging

from eth_typing import (
    Hash32,
)
from eth_utils import (
    encode_hex,
    ValidationError,
)

from eth.db.backends.base import BaseAtomicDB
from eth.exceptions import (
    BlockNotFound,
)
from eth.validation import (
    validate_word,
)

from eth._utils.datatypes import (
    Configurable,
)
from eth._utils.rlp import (
    validate_imported_block_unchanged,
)

from eth.beacon.db.chain import (  # noqa: F401
    BaseBeaconChainDB,
    BeaconChainDB,
)
from eth.beacon.exceptions import (
    SMNotFound,
)
from eth.beacon.state_machines.base import BaseBeaconStateMachine  # noqa: F401
from eth.beacon.types.blocks import (
    BaseBeaconBlock,
    BeaconBlock,
)
from eth.beacon.types.states import BeaconState
from eth.beacon.typing import (
    SlotNumber,
)
from eth.beacon.validation import (
    validate_slot,
)


class BaseBeaconChain(Configurable, ABC):
    """
    The base class for all BeaconChain objects
    """
    chaindb = None  # type: BaseBeaconChainDB
    chaindb_class = None  # type: Type[BaseBeaconChainDB]
    sm_configuration = None  # type: Tuple[Tuple[int, Type[BaseBeaconStateMachine]], ...]
    chain_id = None  # type: int

    #
    # Helpers
    #
    @classmethod
    @abstractmethod
    def get_chaindb_class(cls) -> Type[BaseBeaconChainDB]:
        pass

    @classmethod
    def get_sm_configuration(cls) -> Tuple[Tuple[int, Type['BaseBeaconStateMachine']], ...]:
        return cls.sm_configuration

    #
    # Chain API
    #
    @classmethod
    @abstractmethod
    def from_genesis(cls,
                     base_db: BaseAtomicDB,
                     genesis_state: BeaconState,
                     genesis_block: BaseBeaconBlock) -> 'BaseBeaconChain':
        pass

    @classmethod
    @abstractmethod
    def from_genesis_block(cls,
                           base_db: BaseAtomicDB,
                           genesis_block: BaseBeaconBlock) -> 'BaseBeaconChain':
        pass

    #
    # State Machine API
    #
    @classmethod
    def get_sm_class(cls, block: BaseBeaconBlock) -> Type['BaseBeaconStateMachine']:
        """
        Returns the StateMachine instance for the given block slot number.
        """
        return cls.get_sm_class_for_block_slot(block.slot)

    @abstractmethod
    def get_sm(self, block: BaseBeaconBlock) -> 'BaseBeaconStateMachine':
        raise NotImplementedError("Chain classes must implement this method")

    @classmethod
    def get_sm_class_for_block_slot(cls, slot: SlotNumber) -> Type['BaseBeaconStateMachine']:
        """
        Return the StateMachine class for the given block slot number.
        """
        if cls.sm_configuration is None:
            raise AttributeError("Chain classes must define the StateMachines in sm_configuration")

        validate_slot(slot)
        for start_slot, sm_class in reversed(cls.sm_configuration):
            if slot >= start_slot:
                return sm_class
        raise SMNotFound("No StateMachine available for block slot: #{0}".format(slot))

    #
    # Block API
    #
    @abstractmethod
    def create_block_from_parent(self,
                                 parent_block: BaseBeaconBlock,
                                 **block_params: Any) -> BaseBeaconBlock:
        pass

    @abstractmethod
    def get_block_by_root(self, block_root: Hash32) -> BaseBeaconBlock:
        pass

    @abstractmethod
    def get_canonical_head(self) -> BaseBeaconBlock:
        pass

    @abstractmethod
    def get_score(self, block_root: Hash32) -> int:
        pass

    @abstractmethod
    def ensure_block(self, block: BaseBeaconBlock=None) -> BaseBeaconBlock:
        pass

    @abstractmethod
    def get_block(self) -> BaseBeaconBlock:
        pass

    @abstractmethod
    def get_canonical_block_by_slot(self, slot: SlotNumber) -> BaseBeaconBlock:
        pass

    @abstractmethod
    def get_canonical_block_root(self, slot: SlotNumber) -> Hash32:
        pass

    @abstractmethod
    def import_block(
            self,
            block: BaseBeaconBlock,
            perform_validation: bool=True
    ) -> Tuple[BaseBeaconBlock, Tuple[BaseBeaconBlock, ...], Tuple[BaseBeaconBlock, ...]]:
        pass


class BeaconChain(BaseBeaconChain):
    """
    A Chain is a combination of one or more StateMachine classes.  Each StateMachine is associated
    with a range of blocks.  The Chain class acts as a wrapper around these other
    StateMachine classes, delegating operations to the appropriate StateMachine depending on the
    current block slot number.
    """
    logger = logging.getLogger("eth.beacon.chains.chain.BeaconChain")

    chaindb_class = BeaconChainDB  # type: Type[BaseBeaconChainDB]

    def __init__(self, base_db: BaseAtomicDB) -> None:
        if not self.sm_configuration:
            raise ValueError(
                "The Chain class cannot be instantiated with an empty `sm_configuration`"
            )
        else:
            # TODO implment validate_sm_configuration(self.sm_configuration)
            # validate_sm_configuration(self.sm_configuration)
            pass

        # block_class = BeaconBlock by default
        self.chaindb = self.get_chaindb_class()(base_db, BeaconBlock)

    #
    # Helpers
    #
    @classmethod
    def get_chaindb_class(cls) -> Type['BaseBeaconChainDB']:
        if cls.chaindb_class is None:
            raise AttributeError("`chaindb_class` not set")
        return cls.chaindb_class

    #
    # Chain API
    #
    @classmethod
    def from_genesis(cls,
                     base_db: BaseAtomicDB,
                     genesis_state: BeaconState,
                     genesis_block: BaseBeaconBlock) -> 'BaseBeaconChain':
        """
        Initialize the Chain from a genesis state.
        """
        # mutation
        chaindb = cls.get_chaindb_class()(db=base_db, block_class=genesis_block.__class__)
        chaindb.persist_state(genesis_state)
        return cls.from_genesis_block(base_db, genesis_block)

    @classmethod
    def from_genesis_block(cls,
                           base_db: BaseAtomicDB,
                           genesis_block: BaseBeaconBlock) -> 'BaseBeaconChain':
        """
        Initialize the chain from the genesis block.
        """
        chaindb = cls.get_chaindb_class()(db=base_db, block_class=genesis_block.__class__)
        chaindb.persist_block(genesis_block)
        return cls(base_db)

    #
    # StateMachine API
    #
    def get_sm(self, at_block: BaseBeaconBlock=None) -> 'BaseBeaconStateMachine':
        """
        Return the StateMachine instance for the given block number.
        """
        block = self.ensure_block(at_block)
        sm_class = self.get_sm_class_for_block_slot(block.slot)
        return sm_class(chaindb=self.chaindb, block_root=block.root)

    #
    # Block API
    #
    def create_block_from_parent(self,
                                 parent_block: BaseBeaconBlock,
                                 **block_params: Any) -> BaseBeaconBlock:
        """
        Passthrough helper to the StateMachine class of the block descending from the
        given block.
        """

        return self.get_sm_class_for_block_slot(
            slot=parent_block.slot + 1,
        ).create_block_from_parent(parent_block, **block_params)

    def get_block_by_root(self, block_root: Hash32) -> BaseBeaconBlock:
        """
        Return the requested block as specified by block hash.

        Raise BlockNotFound if there's no block with the given hash in the db.
        """
        validate_word(block_root, title="Block Hash")
        return self.chaindb.get_block_by_root(block_root)

    def get_canonical_head(self) -> BaseBeaconBlock:
        """
        Return the block at the canonical chain head.

        Raise CanonicalHeadNotFound if there's no head defined for the canonical chain.
        """
        return self.chaindb.get_canonical_head()

    def get_score(self, block_root: Hash32) -> int:
        """
        Return the score of the block with the given hash.

        Raises BlockNotFound if there is no matching black hash.
        """
        return self.chaindb.get_score(block_root)

    def ensure_block(self, block: BaseBeaconBlock=None) -> BaseBeaconBlock:
        """
        Return ``block`` if it is not ``None``, otherwise return the block
        of the canonical head.
        """
        if block is None:
            head = self.get_canonical_head()
            return self.create_block_from_parent(head)
        else:
            return block

    def get_block(self) -> BaseBeaconBlock:
        """
        Return the current TIP block.
        """
        return self.get_sm().block

    def get_canonical_block_by_slot(self, slot: SlotNumber) -> BaseBeaconBlock:
        """
        Return the block with the given number in the canonical chain.

        Raise BlockNotFound if there's no block with the given number in the
        canonical chain.
        """
        validate_slot(slot)
        return self.get_block_by_root(self.chaindb.get_canonical_block_root(slot))

    def get_canonical_block_root(self, slot: SlotNumber) -> Hash32:
        """
        Return the block hash with the given number in the canonical chain.

        Raise BlockNotFound if there's no block with the given number in the
        canonical chain.
        """
        return self.chaindb.get_canonical_block_root(slot)

    def import_block(
            self,
            block: BaseBeaconBlock,
            perform_validation: bool=True
    ) -> Tuple[BaseBeaconBlock, Tuple[BaseBeaconBlock, ...], Tuple[BaseBeaconBlock, ...]]:
        """
        Import a complete block and returns a 3-tuple

        - the imported block
        - a tuple of blocks which are now part of the canonical chain.
        - a tuple of blocks which are were canonical and now are no longer canonical.
        """

        try:
            parent_block = self.get_block_by_root(block.parent_hash)
        except BlockNotFound:
            raise ValidationError(
                "Attempt to import block #{}.  Cannot import block {} before importing "
                "its parent block at {}".format(
                    block.slot,
                    block.hash,
                    block.parent_hash,
                )
            )
        base_block_for_import = self.create_block_from_parent(parent_block)
        state, imported_block = self.get_sm(
            base_block_for_import
        ).import_block(block)

        # TODO: deal with state

        # Validate the imported block.
        if perform_validation:
            validate_imported_block_unchanged(imported_block, block)

        (
            new_canonical_blocks,
            old_canonical_blocks,
        ) = self.chaindb.persist_block(imported_block)

        self.logger.debug(
            'IMPORTED_BLOCK: slot %s | hash %s',
            imported_block.slot,
            encode_hex(imported_block.hash),
        )

        return imported_block, new_canonical_blocks, old_canonical_blocks
