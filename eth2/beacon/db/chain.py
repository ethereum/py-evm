from abc import ABC, abstractmethod
import functools

from typing import (
    Iterable,
    Optional,
    Tuple,
    Type,
)
from cytoolz import (
    concat,
    first,
    sliding_window,
)

import ssz
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
    ZERO_HASH32,
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
from eth2.beacon.helpers import (
    slot_to_epoch,
)
from eth2.beacon.typing import (
    Epoch,
    Slot,
)
from eth2.beacon.types.states import BeaconState  # noqa: F401
from eth2.beacon.types.blocks import (  # noqa: F401
    BaseBeaconBlock,
    BeaconBlock,
)
from eth2.beacon.validation import (
    validate_slot,
)

from eth2.beacon.db.exceptions import (
    FinalizedHeadNotFound,
    JustifiedHeadNotFound,
)
from eth2.beacon.db.schema import SchemaV1

from eth2.configs import (
    Eth2GenesisConfig,
)


class BaseBeaconChainDB(ABC):
    db = None  # type: BaseAtomicDB

    @abstractmethod
    def __init__(self, db: BaseAtomicDB, genesis_config: Eth2GenesisConfig) -> None:
        pass

    #
    # Block API
    #
    @abstractmethod
    def persist_block(
            self,
            block: BaseBeaconBlock,
            block_class: Type[BaseBeaconBlock]
    ) -> Tuple[Tuple[BaseBeaconBlock, ...], Tuple[BaseBeaconBlock, ...]]:
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
    def get_canonical_head(self, block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        pass

    @abstractmethod
    def get_canonical_head_root(self) -> Hash32:
        pass

    @abstractmethod
    def get_finalized_head(self, block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        pass

    @abstractmethod
    def get_justified_head(self, block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        pass

    @abstractmethod
    def get_block_by_root(self,
                          block_root: Hash32,
                          block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        pass

    @abstractmethod
    def get_slot_by_root(self,
                         block_root: Hash32) -> Slot:
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
    def get_state_by_root(self, state_root: Hash32, state_class: Type[BeaconState]) -> BeaconState:
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
    def __init__(self, db: BaseAtomicDB, genesis_config: Eth2GenesisConfig) -> None:
        self.db = db
        self.genesis_config = genesis_config

        self._finalized_root = self._get_finalized_root_if_present(db)
        self._highest_justified_epoch = self._get_highest_justified_epoch(db)

    def _get_finalized_root_if_present(self, db: BaseDB) -> Hash32:
        try:
            return self._get_finalized_head_root(db)
        except FinalizedHeadNotFound:
            return ZERO_HASH32

    def _get_highest_justified_epoch(self, db: BaseDB) -> Epoch:
        try:
            justified_head_root = self._get_justified_head_root(db)
            slot = self.get_slot_by_root(justified_head_root)
            return slot_to_epoch(slot, self.genesis_config.SLOTS_PER_EPOCH)
        except JustifiedHeadNotFound:
            return self.genesis_config.GENESIS_EPOCH

    def persist_block(
            self,
            block: BaseBeaconBlock,
            block_class: Type[BaseBeaconBlock]
    ) -> Tuple[Tuple[BaseBeaconBlock, ...], Tuple[BaseBeaconBlock, ...]]:
        """
        Persist the given block.
        """
        with self.db.atomic_batch() as db:
            if block.is_genesis:
                self._handle_exceptional_justification_and_finality(db, block)

            return self._persist_block(db, block, block_class)

    @classmethod
    def _persist_block(
            cls,
            db: 'BaseDB',
            block: BaseBeaconBlock,
            block_class: Type[BaseBeaconBlock]
    ) -> Tuple[Tuple[BaseBeaconBlock, ...], Tuple[BaseBeaconBlock, ...]]:
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
            return ssz.decode(encoded_key, sedes=ssz.sedes.byte_list)

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
        canonical_block_root = cls._get_canonical_block_root(db, slot)
        return cls._get_block_by_root(db, canonical_block_root, block_class)

    def get_canonical_head(self, block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        """
        Return the current block at the head of the chain.
        """
        return self._get_canonical_head(self.db, block_class)

    @classmethod
    def _get_canonical_head(cls,
                            db: BaseDB,
                            block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        canonical_head_root = cls._get_canonical_head_root(db)
        return cls._get_block_by_root(db, Hash32(canonical_head_root), block_class)

    def get_canonical_head_root(self) -> Hash32:
        """
        Return the current block root at the head of the chain.
        """
        return self._get_canonical_head_root(self.db)

    @staticmethod
    def _get_canonical_head_root(db: BaseDB) -> Hash32:
        try:
            canonical_head_root = db[SchemaV1.make_canonical_head_root_lookup_key()]
        except KeyError:
            raise CanonicalHeadNotFound("No canonical head set for this chain")
        return canonical_head_root

    def get_finalized_head(self, block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        """
        Return the finalized head.
        """
        return self._get_finalized_head(self.db, block_class)

    @classmethod
    def _get_finalized_head(cls,
                            db: BaseDB,
                            block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        finalized_head_root = cls._get_finalized_head_root(db)
        return cls._get_block_by_root(db, Hash32(finalized_head_root), block_class)

    @staticmethod
    def _get_finalized_head_root(db: BaseDB) -> Hash32:
        try:
            finalized_head_root = db[SchemaV1.make_finalized_head_root_lookup_key()]
        except KeyError:
            raise FinalizedHeadNotFound("No finalized head set for this chain")
        return finalized_head_root

    def get_justified_head(self, block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        """
        Return the justified head.
        """
        return self._get_justified_head(self.db, block_class)

    @classmethod
    def _get_justified_head(cls,
                            db: BaseDB,
                            block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
        justified_head_root = cls._get_justified_head_root(db)
        return cls._get_block_by_root(db, Hash32(justified_head_root), block_class)

    @staticmethod
    def _get_justified_head_root(db: BaseDB) -> Hash32:
        try:
            justified_head_root = db[SchemaV1.make_justified_head_root_lookup_key()]
        except KeyError:
            raise JustifiedHeadNotFound("No justified head set for this chain")
        return justified_head_root

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
            block_ssz = db[block_root]
        except KeyError:
            raise BlockNotFound("No block with root {0} found".format(
                encode_hex(block_root)))
        return _decode_block(block_ssz, block_class)

    def get_slot_by_root(self,
                         block_root: Hash32) -> Slot:
        """
        Return the requested block header as specified by block root.

        Raise BlockNotFound if it is not present in the db.
        """
        return self._get_slot_by_root(self.db, block_root)

    @staticmethod
    def _get_slot_by_root(db: BaseDB,
                          block_root: Hash32) -> Slot:
        validate_word(block_root, title="block root")
        try:
            encoded_slot = db[SchemaV1.make_block_root_to_slot_lookup_key(block_root)]
        except KeyError:
            raise BlockNotFound("No block with root {0} found".format(
                encode_hex(block_root)))
        return Slot(ssz.decode(encoded_slot, sedes=ssz.sedes.uint64))

    def get_score(self, block_root: Hash32) -> int:
        return self._get_score(self.db, block_root)

    @staticmethod
    def _get_score(db: BaseDB, block_root: Hash32) -> int:
        try:
            encoded_score = db[SchemaV1.make_block_root_to_score_lookup_key(block_root)]
        except KeyError:
            raise BlockNotFound("No block with hash {0} found".format(
                encode_hex(block_root)))
        return ssz.decode(encoded_score, sedes=ssz.sedes.uint64)

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

    @staticmethod
    def _set_block_scores_to_db(
            db: BaseDB,
            block: BaseBeaconBlock
    ) -> int:
        # TODO: It's a stub before we implement fork choice rule
        score = block.slot

        db.set(
            SchemaV1.make_block_root_to_score_lookup_key(block.signing_root),
            ssz.encode(score, sedes=ssz.sedes.uint64),
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

        try:
            previous_canonical_head = cls._get_canonical_head(db, block_class).signing_root
            head_score = cls._get_score(db, previous_canonical_head)
        except CanonicalHeadNotFound:
            no_canonical_head = True
        else:
            no_canonical_head = False

        is_genesis = first_block.is_genesis
        if not is_genesis and not cls._block_exists(db, first_block.previous_block_root):
            raise ParentNotFound(
                "Cannot persist block ({}) with unknown parent ({})".format(
                    encode_hex(first_block.signing_root),
                    encode_hex(first_block.previous_block_root),
                )
            )

        score = first_block.slot

        curr_block_head = first_block
        db.set(
            curr_block_head.signing_root,
            ssz.encode(curr_block_head),
        )
        cls._add_block_root_to_slot_lookup(db, curr_block_head)
        cls._set_block_scores_to_db(db, curr_block_head)

        orig_blocks_seq = concat([(first_block,), blocks_iterator])

        for parent, child in sliding_window(2, orig_blocks_seq):
            if parent.signing_root != child.previous_block_root:
                raise ValidationError(
                    "Non-contiguous chain. Expected {} to have {} as parent but was {}".format(
                        encode_hex(child.signing_root),
                        encode_hex(parent.signing_root),
                        encode_hex(child.previous_block_root),
                    )
                )

            curr_block_head = child
            db.set(
                curr_block_head.signing_root,
                ssz.encode(curr_block_head),
            )
            cls._add_block_root_to_slot_lookup(db, curr_block_head)
            score = cls._set_block_scores_to_db(db, curr_block_head)

        if no_canonical_head:
            return cls._set_as_canonical_chain_head(db, curr_block_head.signing_root, block_class)

        if score > head_score:
            return cls._set_as_canonical_chain_head(db, curr_block_head.signing_root, block_class)
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

        db.set(SchemaV1.make_canonical_head_root_lookup_key(), block.signing_root)

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
                if orig.signing_root == block.signing_root:
                    # Found the common ancestor, stop.
                    break

            # Found a new ancestor
            yield block

            if block.is_genesis:
                break
            else:
                block = cls._get_block_by_root(db, block.previous_block_root, block_class)

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
            ssz.encode(block.signing_root, sedes=ssz.sedes.byte_list),
        )

    @staticmethod
    def _add_block_root_to_slot_lookup(db: BaseDB, block: BaseBeaconBlock) -> None:
        """
        Set a record in the database to allow looking up the slot number by its
        block root.
        """
        block_root_to_slot_key = SchemaV1.make_block_root_to_slot_lookup_key(
            block.signing_root
        )
        db.set(
            block_root_to_slot_key,
            ssz.encode(block.slot, sedes=ssz.sedes.uint64),
        )

    #
    # Beacon State API
    #
    def get_state_by_root(self, state_root: Hash32, state_class: Type[BeaconState]) -> BeaconState:
        return self._get_state_by_root(self.db, state_root, state_class)

    @staticmethod
    def _get_state_by_root(db: BaseDB,
                           state_root: Hash32,
                           state_class: Type[BeaconState]) -> BeaconState:
        """
        Return the requested beacon state as specified by state hash.

        Raises StateRootNotFound if it is not present in the db.
        """
        # TODO: validate_state_root
        try:
            state_ssz = db[state_root]
        except KeyError:
            raise StateRootNotFound(f"No state with root {encode_hex(state_root)} found")
        return _decode_state(state_ssz, state_class)

    def persist_state(self,
                      state: BeaconState) -> None:
        """
        Persist the given BeaconState.

        This includes the finality data contained in the BeaconState.
        """
        return self._persist_state(state)

    def _persist_state(self, state: BeaconState) -> None:
        self.db.set(
            state.root,
            ssz.encode(state),
        )

        self._persist_finalized_head(state)
        self._persist_justified_head(state)

    def _update_finalized_head(self, finalized_root: Hash32) -> None:
        """
        Unconditionally write the ``finalized_root`` as the root of the currently
        finalized block.
        """
        self.db.set(
            SchemaV1.make_finalized_head_root_lookup_key(),
            finalized_root,
        )
        self._finalized_root = finalized_root

    def _persist_finalized_head(self, state: BeaconState) -> None:
        """
        If there is a new ``state.finalized_root``, then we can update it in the DB.
        This policy is safe because a large number of validators on the network
        will have violated a slashing condition if the invariant does not hold.
        """
        if state.finalized_root == ZERO_HASH32:
            # ignore finality in the genesis state
            return

        if state.finalized_root != self._finalized_root:
            self._update_finalized_head(state.finalized_root)

    def _update_justified_head(self, justified_root: Hash32, epoch: Epoch) -> None:
        """
        Unconditionally write the ``justified_root`` as the root of the highest
        justified block.
        """
        self.db.set(
            SchemaV1.make_justified_head_root_lookup_key(),
            justified_root,
        )
        self._highest_justified_epoch = epoch

    def _find_updated_justified_root(self, state: BeaconState) -> Optional[Tuple[Hash32, Epoch]]:
        """
        Find the highest epoch that has been justified so far.

        If:
        (i) we find one higher than the epoch of the current justified head
        and
        (ii) it has been justified for more than one epoch,

        then return that (root, epoch) pair.
        """
        if state.current_justified_epoch > self._highest_justified_epoch:
            return (state.current_justified_root, state.current_justified_epoch)
        elif state.previous_justified_epoch > self._highest_justified_epoch:
            return (state.previous_justified_root, state.previous_justified_epoch)
        return None

    def _persist_justified_head(self, state: BeaconState) -> None:
        """
        If there is a new justified root that has been justified for at least one
        epoch _and_ the justification is for a higher epoch than we have previously
        seen, go ahead and update the justified head.
        """
        result = self._find_updated_justified_root(state)

        if result:
            self._update_justified_head(*result)

    def _handle_exceptional_justification_and_finality(self,
                                                       db: BaseDB,
                                                       genesis_block: BaseBeaconBlock) -> None:
        """
        The genesis ``BeaconState`` lacks the correct justification and finality
        data in the early epochs. The invariants of this class require an exceptional
        handling to mark the genesis block's root and the genesis epoch as
        finalized and justified.
        """
        genesis_root = genesis_block.signing_root
        self._update_finalized_head(genesis_root)
        self._update_justified_head(genesis_root, self.genesis_config.GENESIS_EPOCH)

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
# up recent blocks to validate the chain, and decoding their SSZ representation is
# relatively expensive so we cache that here, but use a small cache because we *should* only
# be looking up recent blocks.
@functools.lru_cache(128)
def _decode_block(block_ssz: bytes, sedes: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
    return ssz.decode(block_ssz, sedes=sedes)


@functools.lru_cache(128)
def _decode_state(state_ssz: bytes, state_class: Type[BeaconState]) -> BeaconState:
    return ssz.decode(state_ssz, sedes=state_class)
