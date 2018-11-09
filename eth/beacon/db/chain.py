from abc import ABC, abstractmethod
import functools

from typing import (
    Iterable,
    Tuple,
)
from cytoolz import (
    first,
    sliding_window,
)

import rlp
from rlp.sedes import (
    CountableList,
)
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
from eth.rlp.sedes import (
    hash32,
)
from eth.validation import (
    validate_word,
)

from eth.beacon.types.active_states import ActiveState  # noqa: F401
from eth.beacon.types.blocks import BaseBeaconBlock  # noqa: F401
from eth.beacon.types.crystallized_states import CrystallizedState  # noqa: F401
from eth.beacon.validation import (
    validate_slot,
)

from eth.beacon.db.schema import SchemaV1


class BaseBeaconChainDB(ABC):
    db = None  # type: BaseAtomicDB

    #
    # Block API
    #
    @abstractmethod
    def persist_block(self,
                      block: BaseBeaconBlock) -> Tuple[Tuple[bytes, ...], Tuple[bytes, ...]]:
        pass

    @abstractmethod
    def get_canonical_block_hash(self, slot: int) -> Hash32:
        pass

    @abstractmethod
    def get_canonical_block_by_slot(self, slot: int) -> BaseBeaconBlock:
        pass

    @abstractmethod
    def get_canonical_block_hash_by_slot(self, slot: int) -> Hash32:
        pass

    @abstractmethod
    def get_canonical_head(self) -> BaseBeaconBlock:
        pass

    @abstractmethod
    def get_block_by_hash(self, block_hash: Hash32) -> BaseBeaconBlock:
        pass

    @abstractmethod
    def get_score(self, block_hash: Hash32) -> int:
        pass

    @abstractmethod
    def block_exists(self, block_hash: Hash32) -> bool:
        pass

    @abstractmethod
    def persist_block_chain(
        self,
        blocks: Iterable[BaseBeaconBlock]
    ) -> Tuple[Tuple[BaseBeaconBlock, ...], Tuple[BaseBeaconBlock, ...]]:
        pass

    #
    # Crystallized State
    #
    @abstractmethod
    def get_crystallized_state_by_root(self, state_root: Hash32) -> CrystallizedState:
        pass

    @abstractmethod
    def get_canonical_crystallized_state_root(self, slot: int) -> Hash32:
        pass

    @abstractmethod
    def persist_crystallized_state(self,
                                   crystallized_state: CrystallizedState) -> None:
        pass

    #
    # Active State
    #
    @abstractmethod
    def get_active_state_by_root(self, state_root: Hash32) -> ActiveState:
        pass

    @abstractmethod
    def get_active_state_root_by_crystallized(self, crystallized_state_root: Hash32) -> Hash32:
        pass

    @abstractmethod
    def persist_active_state(self,
                             active_state: ActiveState,
                             crystallized_state_root: Hash32) -> None:
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

    def persist_block(self,
                      block: BaseBeaconBlock) -> Tuple[Tuple[bytes, ...], Tuple[bytes, ...]]:
        """
        Persist the given block.
        """
        with self.db.atomic_batch() as db:
            return self._persist_block(db, block)

    @classmethod
    def _persist_block(
            cls,
            db: 'BaseDB',
            block: BaseBeaconBlock) -> Tuple[Tuple[bytes, ...], Tuple[bytes, ...]]:
        block_chain = (block, )
        new_canonical_blocks, old_canonical_blocks = cls._persist_block_chain(db, block_chain)

        return new_canonical_blocks, old_canonical_blocks

    #
    #
    # Copied from HeaderDB
    #
    #

    #
    # Canonical Chain API
    #
    def get_canonical_block_hash(self, slot: int) -> Hash32:
        """
        Return the block hash for the canonical block at the given number.

        Raise BlockNotFound if there's no block with the given number in the
        canonical chain.
        """
        return self._get_canonical_block_hash(self.db, slot)

    @staticmethod
    def _get_canonical_block_hash(db: BaseDB, slot: int) -> Hash32:
        validate_slot(slot)
        slot_to_hash_key = SchemaV1.make_block_slot_to_hash_lookup_key(slot)
        try:
            encoded_key = db[slot_to_hash_key]
        except KeyError:
            raise BlockNotFound(
                "No canonical block for block slot #{0}".format(slot)
            )
        else:
            return rlp.decode(encoded_key, sedes=rlp.sedes.binary)

    def get_canonical_block_by_slot(self, slot: int) -> BaseBeaconBlock:
        """
        Return the block with the given slot in the canonical chain.

        Raise BlockNotFound if there's no block with the given slot in the
        canonical chain.
        """
        return self._get_canonical_block_by_slot(self.db, slot)

    @classmethod
    def _get_canonical_block_by_slot(
            cls,
            db: BaseDB,
            slot: int) -> BaseBeaconBlock:
        canonical_block_hash = cls._get_canonical_block_hash_by_slot(db, slot)
        return cls._get_block_by_hash(db, canonical_block_hash)

    def get_canonical_block_hash_by_slot(self, slot: int) -> Hash32:
        """
        Return the block hash with the given slot in the canonical chain.

        Raise BlockNotFound if there's no block with the given slot in the
        canonical chain.
        """
        return self._get_canonical_block_hash_by_slot(self.db, slot)

    @classmethod
    def _get_canonical_block_hash_by_slot(
            cls,
            db: BaseDB,
            slot: int) -> Hash32:
        validate_slot(slot)
        return cls._get_canonical_block_hash(db, slot)

    def get_canonical_head(self) -> BaseBeaconBlock:
        """
        Return the current block at the head of the chain.
        """
        return self._get_canonical_head(self.db)

    @classmethod
    def _get_canonical_head(cls, db: BaseDB) -> BaseBeaconBlock:
        try:
            canonical_head_hash = db[SchemaV1.make_canonical_head_hash_lookup_key()]
        except KeyError:
            raise CanonicalHeadNotFound("No canonical head set for this chain")
        return cls._get_block_by_hash(db, Hash32(canonical_head_hash))

    def get_block_by_hash(self, block_hash: Hash32) -> BaseBeaconBlock:
        return self._get_block_by_hash(self.db, block_hash)

    @staticmethod
    def _get_block_by_hash(db: BaseDB, block_hash: Hash32) -> BaseBeaconBlock:
        """
        Return the requested block header as specified by block hash.

        Raise BlockNotFound if it is not present in the db.
        """
        validate_word(block_hash, title="Block Hash")
        try:
            block_rlp = db[block_hash]
        except KeyError:
            raise BlockNotFound("No block with hash {0} found".format(
                encode_hex(block_hash)))
        return _decode_block(block_rlp)

    def get_score(self, block_hash: Hash32) -> int:
        return self._get_score(self.db, block_hash)

    @staticmethod
    def _get_score(db: BaseDB, block_hash: Hash32) -> int:
        try:
            encoded_score = db[SchemaV1.make_block_hash_to_score_lookup_key(block_hash)]
        except KeyError:
            raise BlockNotFound("No block with hash {0} found".format(
                encode_hex(block_hash)))
        return rlp.decode(encoded_score, sedes=rlp.sedes.big_endian_int)

    def block_exists(self, block_hash: Hash32) -> bool:
        return self._block_exists(self.db, block_hash)

    @staticmethod
    def _block_exists(db: BaseDB, block_hash: Hash32) -> bool:
        validate_word(block_hash, title="Block Hash")
        return block_hash in db

    def persist_block_chain(
        self,
        blocks: Iterable[BaseBeaconBlock]
    ) -> Tuple[Tuple[BaseBeaconBlock, ...], Tuple[BaseBeaconBlock, ...]]:
        """
        Return two iterable of blocks, the first containing the new canonical blocks,
        the second containing the old canonical headers
        """
        with self.db.atomic_batch() as db:
            return self._persist_block_chain(db, blocks)

    @classmethod
    def _persist_block_chain(
            cls,
            db: BaseDB,
            blocks: Iterable[BaseBeaconBlock]
    ) -> Tuple[Tuple[BaseBeaconBlock, ...], Tuple[BaseBeaconBlock, ...]]:
        try:
            first_block = first(blocks)
        except StopIteration:
            return tuple(), tuple()
        else:
            for parent, child in sliding_window(2, blocks):
                if parent.hash != child.parent_hash:
                    raise ValidationError(
                        "Non-contiguous chain. Expected {} to have {} as parent but was {}".format(
                            encode_hex(child.hash),
                            encode_hex(parent.hash),
                            encode_hex(child.parent_hash),
                        )
                    )

            is_genesis = first_block.parent_hash == GENESIS_PARENT_HASH
            if not is_genesis and not cls._block_exists(db, first_block.parent_hash):
                raise ParentNotFound(
                    "Cannot persist block ({}) with unknown parent ({})".format(
                        encode_hex(first_block.hash), encode_hex(first_block.parent_hash)))

            if is_genesis:
                score = 0
            else:
                score = cls._get_score(db, first_block.parent_hash)

        for block in blocks:
            db.set(
                block.hash,
                rlp.encode(block),
            )

            # TODO: It's a stub before we implement fork choice rule
            score += block.slot_number

            db.set(
                SchemaV1.make_block_hash_to_score_lookup_key(block.hash),
                rlp.encode(score, sedes=rlp.sedes.big_endian_int),
            )

        try:
            previous_canonical_head = cls._get_canonical_head(db).hash
            head_score = cls._get_score(db, previous_canonical_head)
        except CanonicalHeadNotFound:
            return cls._set_as_canonical_chain_head(db, block.hash)

        if score > head_score:
            return cls._set_as_canonical_chain_head(db, block.hash)
        else:
            return tuple(), tuple()

    @classmethod
    def _set_as_canonical_chain_head(
            cls, db: BaseDB,
            block_hash: Hash32) -> Tuple[Tuple[BaseBeaconBlock, ...], Tuple[BaseBeaconBlock, ...]]:
        """
        Set the canonical chain HEAD to the block as specified by the
        given block hash.

        :return: a tuple of the blocks that are newly in the canonical chain, and the blocks that
            are no longer in the canonical chain
        """
        try:
            block = cls._get_block_by_hash(db, block_hash)
        except BlockNotFound:
            raise ValueError(
                "Cannot use unknown block hash as canonical head: {}".format(block_hash)
            )

        new_canonical_blocks = tuple(reversed(cls._find_new_ancestors(db, block)))
        old_canonical_blocks = []

        for block in new_canonical_blocks:
            try:
                old_canonical_hash = cls._get_canonical_block_hash(db, block.slot_number)
            except BlockNotFound:
                # no old_canonical block, and no more possible
                break
            else:
                old_canonical_block = cls._get_block_by_hash(db, old_canonical_hash)
                old_canonical_blocks.append(old_canonical_block)

        for block in new_canonical_blocks:
            cls._add_block_slot_to_hash_lookup(db, block)

        db.set(SchemaV1.make_canonical_head_hash_lookup_key(), block.hash)

        return new_canonical_blocks, tuple(old_canonical_blocks)

    @classmethod
    @to_tuple
    def _find_new_ancestors(cls, db: BaseDB, block: BaseBeaconBlock) -> Iterable[BaseBeaconBlock]:
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
                orig = cls._get_canonical_block_by_slot(db, block.slot_number)
            except BlockNotFound:
                # This just means the block is not on the canonical chain.
                pass
            else:
                if orig.hash == block.hash:
                    # Found the common ancestor, stop.
                    break

            # Found a new ancestor
            yield block

            if block.parent_hash == GENESIS_PARENT_HASH:
                break
            else:
                block = cls._get_block_by_hash(db, block.parent_hash)

    @staticmethod
    def _add_block_slot_to_hash_lookup(db: BaseDB, block: BaseBeaconBlock) -> None:
        """
        Set a record in the database to allow looking up this block by its
        block slot.
        """
        block_slot_to_hash_key = SchemaV1.make_block_slot_to_hash_lookup_key(
            block.slot_number
        )
        db.set(
            block_slot_to_hash_key,
            rlp.encode(block.hash, sedes=rlp.sedes.binary),
        )

    #
    # Crystallized State API
    #
    def get_crystallized_state_by_root(self, state_root: Hash32) -> CrystallizedState:
        return self._get_crystallized_state_by_root(self.db, state_root)

    @staticmethod
    def _get_crystallized_state_by_root(db: BaseDB, state_root: Hash32) -> CrystallizedState:
        """
        Return the requested crystallized state as specified by state hash.

        Raises StateRootNotFound if it is not present in the db.
        """
        # TODO: validate_crystallized_state_root
        try:
            state_rlp = db[state_root]
        except KeyError:
            raise StateRootNotFound("No state with root {0} found".format(
                encode_hex(state_rlp)))
        return _decode_crystallized_state(state_rlp)

    def get_canonical_crystallized_state_root(self, slot: int) -> Hash32:
        """
        Return the state hash for the canonical state at the given slot.

        Raises StateRootNotFound if there's no state with the given slot in the
        canonical chain.
        """
        return self._get_canonical_crystallized_state_root(self.db, slot)

    @staticmethod
    def _get_canonical_crystallized_state_root(db: BaseDB, slot: int) -> Hash32:
        validate_slot(slot)
        slot_to_hash_key = SchemaV1.make_slot_to_crystallized_state_lookup_key(slot)
        try:
            encoded_key = db[slot_to_hash_key]
        except KeyError:
            raise StateRootNotFound(
                "No canonical crystallized state for slot #{0}".format(slot)
            )
        else:
            return rlp.decode(encoded_key, sedes=rlp.sedes.binary)

    def persist_crystallized_state(self,
                                   crystallized_state: CrystallizedState) -> None:
        """
        Persist the given CrystallizedState.
        """
        return self._persist_crystallized_state(self.db, crystallized_state)

    @classmethod
    def _persist_crystallized_state(cls,
                                    db: BaseDB,
                                    crystallized_state: CrystallizedState) -> None:
        cls._add_slot_to_crystallized_state_lookup(db, crystallized_state)
        db.set(
            crystallized_state.hash,
            rlp.encode(crystallized_state),
        )

    @classmethod
    def _add_slot_to_crystallized_state_lookup(cls,
                                               db: BaseDB,
                                               crystallized_state: CrystallizedState) -> None:
        """
        Set a record in the database to allow looking up this block by its
        last state recalculation slot.

        If it's a fork, store the old state root in `deletable_state_roots`.
        """
        slot_to_hash_key = SchemaV1.make_slot_to_crystallized_state_lookup_key(
            crystallized_state.last_state_recalc
        )
        if db.exists(slot_to_hash_key):
            deletable_state_roots = cls._get_deletable_state_roots(db)
            replaced_state_root = rlp.decode(db[slot_to_hash_key], sedes=rlp.sedes.binary)
            cls._set_deletatable_state(
                db,
                deletable_state_roots + (replaced_state_root, ),
            )
        db.set(
            slot_to_hash_key,
            rlp.encode(crystallized_state.hash, sedes=rlp.sedes.binary),
        )

    @staticmethod
    def _get_deletable_state_roots(db: BaseDB) -> Tuple[Hash32]:
        """
        Return deletable_state_roots.
        """
        lookup_key = SchemaV1.make_deletable_state_roots_lookup_key()
        if not db.exists(lookup_key):
            db.set(
                lookup_key,
                rlp.encode((), sedes=CountableList(hash32)),
            )
        deletable_state_roots = rlp.decode(db[lookup_key], sedes=CountableList(hash32))

        return deletable_state_roots

    @staticmethod
    def _set_deletatable_state(db: BaseDB, deletable_state_roots: Iterable[Hash32]) -> None:
        """
        Set deletable_state_roots.
        """
        lookup_key = SchemaV1.make_deletable_state_roots_lookup_key()
        db.set(
            lookup_key,
            rlp.encode(deletable_state_roots, sedes=CountableList(hash32)),
        )

    #
    # Active State API
    #
    def get_active_state_by_root(self, state_root: Hash32) -> ActiveState:
        return self._get_active_state_by_root(self.db, state_root)

    @staticmethod
    def _get_active_state_by_root(db: BaseDB, state_root: Hash32) -> ActiveState:
        """
        Return the requested crystallized state as specified by state hash.

        Raises StateRootNotFound if it is not present in the db.
        """
        # TODO: validate_active_state_root
        try:
            state_rlp = db[state_root]
        except KeyError:
            raise StateRootNotFound("No state with root {0} found".format(
                encode_hex(state_rlp)))
        return _decode_active_state(state_rlp)

    def get_active_state_root_by_crystallized(self, crystallized_state_root: Hash32) -> Hash32:
        """
        Return the state hash for the canonical state at the given crystallized_state_root.

        Raises StateRootNotFound if there's no state with the given slot in the
        canonical chain.
        """
        return self._get_active_state_root_by_crystallized(self.db, crystallized_state_root)

    @staticmethod
    def _get_active_state_root_by_crystallized(db: BaseDB,
                                               crystallized_state_root: Hash32) -> Hash32:
        state_root_to_hash_key = SchemaV1.make_crystallized_to_active_state_root_lookup_key(
            crystallized_state_root
        )
        try:
            encoded_key = db[state_root_to_hash_key]
        except KeyError:
            raise StateRootNotFound(
                "No canonical active state for crystallized_state_root #{0}".format(
                    state_root_to_hash_key
                )
            )
        else:
            return rlp.decode(encoded_key, sedes=rlp.sedes.binary)

    def persist_active_state(self,
                             active_state: ActiveState,
                             crystallized_state_root: Hash32) -> None:
        """
        Persist the given ActiveState.

        NOTE: only persist active state when recalcuate crystallized state.
        """
        return self._persist_active_state(self.db, active_state, crystallized_state_root)

    @classmethod
    def _persist_active_state(cls,
                              db: BaseDB,
                              active_state: ActiveState,
                              crystallized_state_root: Hash32) -> None:
        cls._add_crystallized_to_active_state_lookup(db, active_state, crystallized_state_root)
        db.set(
            active_state.hash,
            rlp.encode(active_state),
        )

    @classmethod
    def _add_crystallized_to_active_state_lookup(cls,
                                                 db: BaseDB,
                                                 active_state: ActiveState,
                                                 crystallized_state_root: Hash32) -> None:
        """
        Set a record in the database to allow looking up this block by its
        last state recalculation slot.
        """
        slot_to_hash_key = SchemaV1.make_crystallized_to_active_state_root_lookup_key(
            crystallized_state_root,
        )
        db.set(
            slot_to_hash_key,
            rlp.encode(active_state.hash, sedes=rlp.sedes.binary),
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
def _decode_block(block_rlp: bytes) -> BaseBeaconBlock:
    # TODO: forkable Block fields?
    return rlp.decode(block_rlp, sedes=BaseBeaconBlock)


@functools.lru_cache(128)
def _decode_crystallized_state(crystallized_state_rlp: bytes) -> CrystallizedState:
    # TODO: forkable CrystallizedState fields?
    return rlp.decode(crystallized_state_rlp, sedes=CrystallizedState)


@functools.lru_cache(128)
def _decode_active_state(active_state_rlp: bytes) -> ActiveState:
    # TODO: forkable CrystallizedState fields?
    return rlp.decode(active_state_rlp, sedes=ActiveState)
