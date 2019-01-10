from abc import ABC, abstractmethod
import functools
from typing import Iterable, Tuple

import rlp

from eth_utils.toolz import (
    concat,
    first,
    sliding_window,
)

from eth_utils import (
    encode_hex,
    to_tuple,
    ValidationError,
)

from eth_typing import (
    Hash32,
    BlockNumber,
)

from eth.constants import (
    GENESIS_PARENT_HASH,
)
from eth.exceptions import (
    CanonicalHeadNotFound,
    HeaderNotFound,
    ParentNotFound,
)
from eth.db.backends.base import (
    BaseAtomicDB,
    BaseDB,
)
from eth.db.schema import SchemaV1
from eth.rlp.headers import BlockHeader
from eth.validation import (
    validate_block_number,
    validate_word,
)


class BaseHeaderDB(ABC):
    db = None  # type: BaseAtomicDB

    def __init__(self, db: BaseAtomicDB) -> None:
        self.db = db

    #
    # Canonical Chain API
    #
    @abstractmethod
    def get_canonical_block_hash(self, block_number: BlockNumber) -> Hash32:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def get_canonical_block_header_by_number(self, block_number: BlockNumber) -> BlockHeader:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def get_canonical_head(self) -> BlockHeader:
        raise NotImplementedError("ChainDB classes must implement this method")

    #
    # Header API
    #
    @abstractmethod
    def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def get_score(self, block_hash: Hash32) -> int:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def header_exists(self, block_hash: Hash32) -> bool:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def persist_header(self,
                       header: BlockHeader
                       ) -> Tuple[Tuple[BlockHeader, ...], Tuple[BlockHeader, ...]]:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def persist_header_chain(self,
                             headers: Iterable[BlockHeader]
                             ) -> Tuple[Tuple[BlockHeader, ...], Tuple[BlockHeader, ...]]:
        raise NotImplementedError("ChainDB classes must implement this method")


class HeaderDB(BaseHeaderDB):
    #
    # Canonical Chain API
    #
    def get_canonical_block_hash(self, block_number: BlockNumber) -> Hash32:
        """
        Returns the block hash for the canonical block at the given number.

        Raises BlockNotFound if there's no block header with the given number in the
        canonical chain.
        """
        return self._get_canonical_block_hash(self.db, block_number)

    @staticmethod
    def _get_canonical_block_hash(db: BaseDB, block_number: BlockNumber) -> Hash32:
        validate_block_number(block_number)
        number_to_hash_key = SchemaV1.make_block_number_to_hash_lookup_key(block_number)

        try:
            encoded_key = db[number_to_hash_key]
        except KeyError:
            raise HeaderNotFound(
                "No canonical header for block number #{0}".format(block_number)
            )
        else:
            return rlp.decode(encoded_key, sedes=rlp.sedes.binary)

    def get_canonical_block_header_by_number(self, block_number: BlockNumber) -> BlockHeader:
        """
        Returns the block header with the given number in the canonical chain.

        Raises BlockNotFound if there's no block header with the given number in the
        canonical chain.
        """
        return self._get_canonical_block_header_by_number(self.db, block_number)

    @classmethod
    def _get_canonical_block_header_by_number(
            cls,
            db: BaseDB,
            block_number: BlockNumber) -> BlockHeader:
        validate_block_number(block_number)
        canonical_block_hash = cls._get_canonical_block_hash(db, block_number)
        return cls._get_block_header_by_hash(db, canonical_block_hash)

    def get_canonical_head(self) -> BlockHeader:
        """
        Returns the current block header at the head of the chain.
        """
        return self._get_canonical_head(self.db)

    @classmethod
    def _get_canonical_head(cls, db: BaseDB) -> BlockHeader:
        try:
            canonical_head_hash = db[SchemaV1.make_canonical_head_hash_lookup_key()]
        except KeyError:
            raise CanonicalHeadNotFound("No canonical head set for this chain")
        return cls._get_block_header_by_hash(db, Hash32(canonical_head_hash))

    #
    # Header API
    #
    def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        return self._get_block_header_by_hash(self.db, block_hash)

    @staticmethod
    def _get_block_header_by_hash(db: BaseDB, block_hash: Hash32) -> BlockHeader:
        """
        Returns the requested block header as specified by block hash.

        Raises BlockNotFound if it is not present in the db.
        """
        validate_word(block_hash, title="Block Hash")
        try:
            header_rlp = db[block_hash]
        except KeyError:
            raise HeaderNotFound("No header with hash {0} found".format(
                encode_hex(block_hash)))
        return _decode_block_header(header_rlp)

    def get_score(self, block_hash: Hash32) -> int:
        return self._get_score(self.db, block_hash)

    @staticmethod
    def _get_score(db: BaseDB, block_hash: Hash32) -> int:
        try:
            encoded_score = db[SchemaV1.make_block_hash_to_score_lookup_key(block_hash)]
        except KeyError:
            raise HeaderNotFound("No header with hash {0} found".format(
                encode_hex(block_hash)))
        return rlp.decode(encoded_score, sedes=rlp.sedes.big_endian_int)

    def header_exists(self, block_hash: Hash32) -> bool:
        return self._header_exists(self.db, block_hash)

    @staticmethod
    def _header_exists(db: BaseDB, block_hash: Hash32) -> bool:
        validate_word(block_hash, title="Block Hash")
        return block_hash in db

    def persist_header(self,
                       header: BlockHeader
                       ) -> Tuple[Tuple[BlockHeader, ...], Tuple[BlockHeader, ...]]:
        return self.persist_header_chain((header,))

    def persist_header_chain(self,
                             headers: Iterable[BlockHeader]
                             ) -> Tuple[Tuple[BlockHeader, ...], Tuple[BlockHeader, ...]]:
        """
        Return two iterable of headers, the first containing the new canonical headers,
        the second containing the old canonical headers
        """
        with self.db.atomic_batch() as db:
            return self._persist_header_chain(db, headers)

    @classmethod
    def _set_hash_scores_to_db(
            cls,
            db: BaseDB,
            header: BlockHeader,
            score: int
    ) -> int:
        new_score = score + header.difficulty

        db.set(
            SchemaV1.make_block_hash_to_score_lookup_key(header.hash),
            rlp.encode(new_score, sedes=rlp.sedes.big_endian_int),
        )

        return new_score

    @classmethod
    def _persist_header_chain(
            cls,
            db: BaseDB,
            headers: Iterable[BlockHeader]
    ) -> Tuple[Tuple[BlockHeader, ...], Tuple[BlockHeader, ...]]:
        headers_iterator = iter(headers)

        try:
            first_header = first(headers_iterator)
        except StopIteration:
            return tuple(), tuple()

        is_genesis = first_header.parent_hash == GENESIS_PARENT_HASH
        if not is_genesis and not cls._header_exists(db, first_header.parent_hash):
            raise ParentNotFound(
                "Cannot persist block header ({}) with unknown parent ({})".format(
                    encode_hex(first_header.hash), encode_hex(first_header.parent_hash)))

        if is_genesis:
            score = 0
        else:
            score = cls._get_score(db, first_header.parent_hash)

        curr_chain_head = first_header
        db.set(
            curr_chain_head.hash,
            rlp.encode(curr_chain_head),
        )
        score = cls._set_hash_scores_to_db(db, curr_chain_head, score)

        orig_headers_seq = concat([(first_header,), headers_iterator])
        for parent, child in sliding_window(2, orig_headers_seq):
            if parent.hash != child.parent_hash:
                raise ValidationError(
                    "Non-contiguous chain. Expected {} to have {} as parent but was {}".format(
                        encode_hex(child.hash),
                        encode_hex(parent.hash),
                        encode_hex(child.parent_hash),
                    )
                )

            curr_chain_head = child
            db.set(
                curr_chain_head.hash,
                rlp.encode(curr_chain_head),
            )

            score = cls._set_hash_scores_to_db(db, curr_chain_head, score)

        try:
            previous_canonical_head = cls._get_canonical_head(db).hash
            head_score = cls._get_score(db, previous_canonical_head)
        except CanonicalHeadNotFound:
            return cls._set_as_canonical_chain_head(db, curr_chain_head.hash)

        if score > head_score:
            return cls._set_as_canonical_chain_head(db, curr_chain_head.hash)

        return tuple(), tuple()

    @classmethod
    def _set_as_canonical_chain_head(cls, db: BaseDB, block_hash: Hash32
                                     ) -> Tuple[Tuple[BlockHeader, ...], Tuple[BlockHeader, ...]]:
        """
        Sets the canonical chain HEAD to the block header as specified by the
        given block hash.

        :return: a tuple of the headers that are newly in the canonical chain, and the headers that
            are no longer in the canonical chain
        """
        try:
            header = cls._get_block_header_by_hash(db, block_hash)
        except HeaderNotFound:
            raise ValueError(
                "Cannot use unknown block hash as canonical head: {}".format(block_hash)
            )

        new_canonical_headers = tuple(reversed(cls._find_new_ancestors(db, header)))
        old_canonical_headers = []

        for h in new_canonical_headers:
            try:
                old_canonical_hash = cls._get_canonical_block_hash(db, h.block_number)
            except HeaderNotFound:
                # no old_canonical block, and no more possible
                break
            else:
                old_canonical_header = cls._get_block_header_by_hash(db, old_canonical_hash)
                old_canonical_headers.append(old_canonical_header)

        for h in new_canonical_headers:
            cls._add_block_number_to_hash_lookup(db, h)

        db.set(SchemaV1.make_canonical_head_hash_lookup_key(), header.hash)

        return new_canonical_headers, tuple(old_canonical_headers)

    @classmethod
    @to_tuple
    def _find_new_ancestors(cls, db: BaseDB, header: BlockHeader) -> Iterable[BlockHeader]:
        """
        Returns the chain leading up from the given header until (but not including)
        the first ancestor it has in common with our canonical chain.

        If D is the canonical head in the following chain, and F is the new header,
        then this function returns (F, E).

        A - B - C - D
               \
                E - F
        """
        h = header
        while True:
            try:
                orig = cls._get_canonical_block_header_by_number(db, h.block_number)
            except HeaderNotFound:
                # This just means the block is not on the canonical chain.
                pass
            else:
                if orig.hash == h.hash:
                    # Found the common ancestor, stop.
                    break

            # Found a new ancestor
            yield h

            if h.parent_hash == GENESIS_PARENT_HASH:
                break
            else:
                h = cls._get_block_header_by_hash(db, h.parent_hash)

    @staticmethod
    def _add_block_number_to_hash_lookup(db: BaseDB, header: BlockHeader) -> None:
        """
        Sets a record in the database to allow looking up this header by its
        block number.
        """
        block_number_to_hash_key = SchemaV1.make_block_number_to_hash_lookup_key(
            header.block_number
        )
        db.set(
            block_number_to_hash_key,
            rlp.encode(header.hash, sedes=rlp.sedes.binary),
        )


class AsyncHeaderDB(HeaderDB):
    async def coro_get_score(self, block_hash: Hash32) -> int:
        raise NotImplementedError()

    async def coro_get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        raise NotImplementedError()

    async def coro_get_canonical_head(self) -> BlockHeader:
        raise NotImplementedError()

    async def coro_get_canonical_block_header_by_number(
            self, block_number: BlockNumber) -> BlockHeader:
        raise NotImplementedError()

    async def coro_header_exists(self, block_hash: Hash32) -> bool:
        raise NotImplementedError()

    async def coro_get_canonical_block_hash(self, block_number: BlockNumber) -> Hash32:
        raise NotImplementedError()

    async def coro_persist_header(self, header: BlockHeader) -> Tuple[BlockHeader, ...]:
        raise NotImplementedError()

    async def coro_persist_header_chain(self,
                                        headers: Iterable[BlockHeader]) -> Tuple[BlockHeader, ...]:
        raise NotImplementedError()


# When performing a chain sync (either fast or regular modes), we'll very often need to look
# up recent block headers to validate the chain, and decoding their RLP representation is
# relatively expensive so we cache that here, but use a small cache because we *should* only
# be looking up recent blocks.
@functools.lru_cache(128)
def _decode_block_header(header_rlp: bytes) -> BlockHeader:
    return rlp.decode(header_rlp, sedes=BlockHeader)
