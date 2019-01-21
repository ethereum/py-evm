from abc import ABC, abstractmethod
import functools

from typing import (
    Iterable,
    Tuple,
    Type,
)
from cytoolz import (
    concat,
    first,
    sliding_window,
)

import rlp
from eth_typing import (
    Hash32,
)
from eth_utils import (
    encode_hex,
    to_tuple,
    ValidationError,
)

from eth.db.backends.base import (
    BaseAtomicDB,
    BaseDB,
)
from eth.constants import (
    GENESIS_PARENT_HASH,
)
from eth.exceptions import (
    BlockNotFound,
    CanonicalHeadNotFound,
    ParentNotFound,
    StateRootNotFound,
)
from eth.validation import (
    validate_word,
)

from eth2.beacon.types.states import BeaconState  # noqa: F401
from eth2.beacon.types.blocks import (  # noqa: F401
    BaseBeaconBlock,
    BeaconBlock,
)
from eth2.beacon.validation import (
    validate_slot,
)

from eth2.beacon.db.schema import SchemaV1


class BaseBeaconChainDB(ABC):
    db = None  # type: BaseAtomicDB

    #
    # Block API
    #
    @abstractmethod
    def persist_block(
            self,
            block: BaseBeaconBlock,
            block_class: Type[BaseBeaconBlock]
    ) -> Tuple[Tuple[bytes, ...], Tuple[bytes, ...]]:
        pass

    @abstractmethod
    def get_canonical_block_root(self, slot: int) -> Hash32:
        pass

    @abstractmethod
    def get_canonical_block_by_slot(self,
                                    slot: int,
                                    block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        pass

    @abstractmethod
    def get_canonical_block_root_by_slot(self, slot: int) -> Hash32:
        pass

    @abstractmethod
    def get_canonical_head(self, block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        pass

    @abstractmethod
    def get_finalized_head(self, block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        pass

    @abstractmethod
    def get_block_by_root(self,
                          block_root: Hash32,
                          block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        pass

    @abstractmethod
    def get_score(self, block_root: Hash32) -> int:
        pass

    @abstractmethod
    def block_exists(self, block_root: Hash32) -> bool:
        pass

    @abstractmethod
    def persist_block_chain(
            self,
            blocks: Iterable[BaseBeaconBlock],
            block_class: Type[BaseBeaconBlock]
    ) -> Tuple[Tuple[BaseBeaconBlock, ...], Tuple[BaseBeaconBlock, ...]]:
        pass

    #
    # Beacon State
    #
    @abstractmethod
    def get_state_by_root(self, state_root: Hash32) -> BeaconState:
        pass

    @abstractmethod
    def persist_state(self,
                      state: BeaconState) -> None:
        pass

    #
    # Raw Database API
    #
    @abstractmethod
    def exists(self, key: bytes) -> bool:
        pass

    @abstractmethod
    def get(self, key: bytes) -> bytes:
        pass


class BeaconChainDB(BaseBeaconChainDB):
    def __init__(self, db: BaseAtomicDB) -> None:
        self.db = db

    def persist_block(
            self,
            block: BaseBeaconBlock,
            block_class: Type[BaseBeaconBlock]
    ) -> Tuple[Tuple[bytes, ...], Tuple[bytes, ...]]:
        """
        Persist the given block.
        """
        with self.db.atomic_batch() as db:
            return self._persist_block(db, block, block_class)

    @classmethod
    def _persist_block(
            cls,
            db: 'BaseDB',
            block: BaseBeaconBlock,
            block_class: Type[BaseBeaconBlock]) -> Tuple[Tuple[bytes, ...], Tuple[bytes, ...]]:
        block_chain = (block, )
        new_canonical_blocks, old_canonical_blocks = cls._persist_block_chain(
            db,
            block_chain,
            block_class,
        )

        return new_canonical_blocks, old_canonical_blocks

    #
    #
    # Copied from HeaderDB
    #
    #

    #
    # Canonical Chain API
    #
    def get_canonical_block_root(self, slot: int) -> Hash32:
        """
        Return the block root for the canonical block at the given number.

        Raise BlockNotFound if there's no block with the given number in the
        canonical chain.
        """
        return self._get_canonical_block_root(self.db, slot)

    @staticmethod
    def _get_canonical_block_root(db: BaseDB, slot: int) -> Hash32:
        validate_slot(slot)
        slot_to_root_key = SchemaV1.make_block_slot_to_root_lookup_key(slot)
        try:
            encoded_key = db[slot_to_root_key]
        except KeyError:
            raise BlockNotFound(
                "No canonical block for block slot #{0}".format(slot)
            )
        else:
            return rlp.decode(encoded_key, sedes=rlp.sedes.binary)

    def get_canonical_block_by_slot(self,
                                    slot: int,
                                    block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        """
        Return the block with the given slot in the canonical chain.

        Raise BlockNotFound if there's no block with the given slot in the
        canonical chain.
        """
        return self._get_canonical_block_by_slot(self.db, slot, block_class)

    @classmethod
    def _get_canonical_block_by_slot(
            cls,
            db: BaseDB,
            slot: int,
            block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        canonical_block_root = cls._get_canonical_block_root_by_slot(db, slot)
        return cls._get_block_by_root(db, canonical_block_root, block_class)

    def get_canonical_block_root_by_slot(self, slot: int) -> Hash32:
        """
        Return the block root with the given slot in the canonical chain.

        Raise BlockNotFound if there's no block with the given slot in the
        canonical chain.
        """
        return self._get_canonical_block_root_by_slot(self.db, slot)

    @classmethod
    def _get_canonical_block_root_by_slot(
            cls,
            db: BaseDB,
            slot: int) -> Hash32:
        validate_slot(slot)
        return cls._get_canonical_block_root(db, slot)

    def get_canonical_head(self, block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        """
        Return the current block at the head of the chain.
        """
        return self._get_canonical_head(self.db, block_class)

    @classmethod
    def _get_canonical_head(cls,
                            db: BaseDB,
                            block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        try:
            canonical_head_root = db[SchemaV1.make_canonical_head_root_lookup_key()]
        except KeyError:
            raise CanonicalHeadNotFound("No canonical head set for this chain")
        return cls._get_block_by_root(db, Hash32(canonical_head_root), block_class)

    def get_finalized_head(self, block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        """
        Return the finalized head.
        """
        return self._get_finalized_head(self.db, block_class)

    @classmethod
    def _get_finalized_head(cls,
                            db: BaseDB,
                            block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        try:
            finalized_head_root = db[SchemaV1.make_finalized_head_root_lookup_key()]
        except KeyError:
            raise CanonicalHeadNotFound("No finalized head set for this chain")
        return cls._get_block_by_root(db, Hash32(finalized_head_root), block_class)

    def get_block_by_root(self,
                          block_root: Hash32,
                          block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        return self._get_block_by_root(self.db, block_root, block_class)

    @staticmethod
    def _get_block_by_root(db: BaseDB,
                           block_root: Hash32,
                           block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        """
        Return the requested block header as specified by block root.

        Raise BlockNotFound if it is not present in the db.
        """
        validate_word(block_root, title="block root")
        try:
            block_rlp = db[block_root]
        except KeyError:
            raise BlockNotFound("No block with root {0} found".format(
                encode_hex(block_root)))
        return _decode_block(block_rlp, block_class)

    def get_score(self, block_root: Hash32) -> int:
        return self._get_score(self.db, block_root)

    @staticmethod
    def _get_score(db: BaseDB, block_root: Hash32) -> int:
        try:
            encoded_score = db[SchemaV1.make_block_root_to_score_lookup_key(block_root)]
        except KeyError:
            raise BlockNotFound("No block with hash {0} found".format(
                encode_hex(block_root)))
        return rlp.decode(encoded_score, sedes=rlp.sedes.big_endian_int)

    def block_exists(self, block_root: Hash32) -> bool:
        return self._block_exists(self.db, block_root)

    @staticmethod
    def _block_exists(db: BaseDB, block_root: Hash32) -> bool:
        validate_word(block_root, title="block root")
        return block_root in db

    def persist_block_chain(
            self,
            blocks: Iterable[BaseBeaconBlock],
            block_class: Type[BaseBeaconBlock]
    ) -> Tuple[Tuple[BaseBeaconBlock, ...], Tuple[BaseBeaconBlock, ...]]:
        """
        Return two iterable of blocks, the first containing the new canonical blocks,
        the second containing the old canonical headers
        """
        with self.db.atomic_batch() as db:
            return self._persist_block_chain(db, blocks, block_class)

    @classmethod
    def _set_block_scores_to_db(
            cls,
            db: BaseDB,
            block: BaseBeaconBlock
    ) -> int:
        # TODO: It's a stub before we implement fork choice rule
        score = block.slot

        db.set(
            SchemaV1.make_block_root_to_score_lookup_key(block.root),
            rlp.encode(score, sedes=rlp.sedes.big_endian_int),
        )
        return score

    @classmethod
    def _persist_block_chain(
            cls,
            db: BaseDB,
            blocks: Iterable[BaseBeaconBlock],
            block_class: Type[BaseBeaconBlock]
    ) -> Tuple[Tuple[BaseBeaconBlock, ...], Tuple[BaseBeaconBlock, ...]]:
        blocks_iterator = iter(blocks)

        try:
            first_block = first(blocks_iterator)
        except StopIteration:
            return tuple(), tuple()

        is_genesis = first_block.parent_root == GENESIS_PARENT_HASH
        if not is_genesis and not cls._block_exists(db, first_block.parent_root):
            raise ParentNotFound(
                "Cannot persist block ({}) with unknown parent ({})".format(
                    encode_hex(first_block.root), encode_hex(first_block.parent_root)))

        if is_genesis:
            score = 0
            # TODO: this should probably be done as part of the fork choice rule processing
            db.set(
                SchemaV1.make_finalized_head_root_lookup_key(),
                first_block.hash,
            )
        else:
            score = cls._get_score(db, first_block.parent_root)

        curr_block_head = first_block
        db.set(
            curr_block_head.root,
            rlp.encode(curr_block_head),
        )
        cls._set_block_scores_to_db(db, curr_block_head)

        orig_blocks_seq = concat([(first_block,), blocks_iterator])

        for parent, child in sliding_window(2, orig_blocks_seq):
            if parent.root != child.parent_root:
                raise ValidationError(
                    "Non-contiguous chain. Expected {} to have {} as parent but was {}".format(
                        encode_hex(child.root),
                        encode_hex(parent.root),
                        encode_hex(child.parent_root),
                    )
                )

            curr_block_head = child
            db.set(
                curr_block_head.root,
                rlp.encode(curr_block_head),
            )
            score = cls._set_block_scores_to_db(db, curr_block_head)

        try:
            previous_canonical_head = cls._get_canonical_head(db, block_class).root
            head_score = cls._get_score(db, previous_canonical_head)
        except CanonicalHeadNotFound:
            return cls._set_as_canonical_chain_head(db, curr_block_head.root, block_class)

        if score > head_score:
            return cls._set_as_canonical_chain_head(db, curr_block_head.root, block_class)
        else:
            return tuple(), tuple()

    @classmethod
    def _set_as_canonical_chain_head(
            cls,
            db: BaseDB,
            block_root: Hash32,
            block_class: Type[BaseBeaconBlock]
    ) -> Tuple[Tuple[BaseBeaconBlock, ...], Tuple[BaseBeaconBlock, ...]]:
        """
        Set the canonical chain HEAD to the block as specified by the
        given block root.

        :return: a tuple of the blocks that are newly in the canonical chain, and the blocks that
            are no longer in the canonical chain
        """
        try:
            block = cls._get_block_by_root(db, block_root, block_class)
        except BlockNotFound:
            raise ValueError(
                "Cannot use unknown block root as canonical head: {}".format(block_root)
            )

        new_canonical_blocks = tuple(reversed(cls._find_new_ancestors(db, block, block_class)))
        old_canonical_blocks = []

        for block in new_canonical_blocks:
            try:
                old_canonical_root = cls._get_canonical_block_root(db, block.slot)
            except BlockNotFound:
                # no old_canonical block, and no more possible
                break
            else:
                old_canonical_block = cls._get_block_by_root(db, old_canonical_root, block_class)
                old_canonical_blocks.append(old_canonical_block)

        for block in new_canonical_blocks:
            cls._add_block_slot_to_root_lookup(db, block)

        db.set(SchemaV1.make_canonical_head_root_lookup_key(), block.root)

        return new_canonical_blocks, tuple(old_canonical_blocks)

    @classmethod
    @to_tuple
    def _find_new_ancestors(
            cls,
            db: BaseDB,
            block: BaseBeaconBlock,
            block_class: Type[BaseBeaconBlock]) -> Iterable[BaseBeaconBlock]:
        """
        Return the chain leading up from the given block until (but not including)
        the first ancestor it has in common with our canonical chain.

        If D is the canonical head in the following chain, and F is the new block,
        then this function returns (F, E).

        A - B - C - D
               \
                E - F
        """
        while True:
            try:
                orig = cls._get_canonical_block_by_slot(db, block.slot, block_class)
            except BlockNotFound:
                # This just means the block is not on the canonical chain.
                pass
            else:
                if orig.root == block.root:
                    # Found the common ancestor, stop.
                    break

            # Found a new ancestor
            yield block

            if block.parent_root == GENESIS_PARENT_HASH:
                break
            else:
                block = cls._get_block_by_root(db, block.parent_root, block_class)

    @staticmethod
    def _add_block_slot_to_root_lookup(db: BaseDB, block: BaseBeaconBlock) -> None:
        """
        Set a record in the database to allow looking up this block by its
        block slot.
        """
        block_slot_to_root_key = SchemaV1.make_block_slot_to_root_lookup_key(
            block.slot
        )
        db.set(
            block_slot_to_root_key,
            rlp.encode(block.root, sedes=rlp.sedes.binary),
        )

    #
    # Beacon State API
    #
    def get_state_by_root(self, state_root: Hash32) -> BeaconState:
        return self._get_state_by_root(self.db, state_root)

    @staticmethod
    def _get_state_by_root(db: BaseDB, state_root: Hash32) -> BeaconState:
        """
        Return the requested beacon state as specified by state hash.

        Raises StateRootNotFound if it is not present in the db.
        """
        # TODO: validate_state_root
        try:
            state_rlp = db[state_root]
        except KeyError:
            raise StateRootNotFound("No state with root {0} found".format(
                encode_hex(state_rlp)))
        return _decode_state(state_rlp)

    def persist_state(self,
                      state: BeaconState) -> None:
        """
        Persist the given BeaconState.
        """
        return self._persist_state(self.db, state)

    @classmethod
    def _persist_state(cls,
                       db: BaseDB,
                       state: BeaconState) -> None:
        db.set(
            state.root,
            rlp.encode(state),
        )

    #
    # Raw Database API
    #
    def exists(self, key: bytes) -> bool:
        """
        Return True if the given key exists in the database.
        """
        return self.db.exists(key)

    def get(self, key: bytes) -> bytes:
        """
        Return the value for the given key or a KeyError if it doesn't exist in the database.
        """
        return self.db[key]


# When performing a chain sync (either fast or regular modes), we'll very often need to look
# up recent blocks to validate the chain, and decoding their RLP representation is
# relatively expensive so we cache that here, but use a small cache because we *should* only
# be looking up recent blocks.
@functools.lru_cache(128)
def _decode_block(block_rlp: bytes, sedes: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
    return rlp.decode(block_rlp, sedes=sedes)


@functools.lru_cache(128)
def _decode_state(state_rlp: bytes) -> BeaconState:
    # TODO: forkable BeaconState fields?
    return rlp.decode(state_rlp, sedes=BeaconState)
