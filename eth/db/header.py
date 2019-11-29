import functools
from typing import cast, Iterable, Tuple

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

from eth.abc import (
    AtomicDatabaseAPI,
    BlockHeaderAPI,
    DatabaseAPI,
    HeaderDatabaseAPI,
)
from eth.constants import (
    GENESIS_PARENT_HASH,
)
from eth.exceptions import (
    CanonicalHeadNotFound,
    HeaderNotFound,
    ParentNotFound,
)
from eth.db.schema import SchemaV1
from eth.rlp.headers import BlockHeader
from eth.validation import (
    validate_block_number,
    validate_word,
)


class HeaderDB(HeaderDatabaseAPI):
    def __init__(self, db: AtomicDatabaseAPI) -> None:
        self.db = db

    #
    # Canonical Chain API
    #
    def get_canonical_block_hash(self, block_number: BlockNumber) -> Hash32:
        return self._get_canonical_block_hash(self.db, block_number)

    @staticmethod
    def _get_canonical_block_hash(db: DatabaseAPI, block_number: BlockNumber) -> Hash32:
        validate_block_number(block_number)
        number_to_hash_key = SchemaV1.make_block_number_to_hash_lookup_key(block_number)

        try:
            encoded_key = db[number_to_hash_key]
        except KeyError:
            raise HeaderNotFound(
                f"No canonical header for block number #{block_number}"
            )
        else:
            return rlp.decode(encoded_key, sedes=rlp.sedes.binary)

    def get_canonical_block_header_by_number(self, block_number: BlockNumber) -> BlockHeaderAPI:
        return self._get_canonical_block_header_by_number(self.db, block_number)

    @classmethod
    def _get_canonical_block_header_by_number(
            cls,
            db: DatabaseAPI,
            block_number: BlockNumber) -> BlockHeaderAPI:
        validate_block_number(block_number)
        canonical_block_hash = cls._get_canonical_block_hash(db, block_number)
        return cls._get_block_header_by_hash(db, canonical_block_hash)

    def get_canonical_head(self) -> BlockHeaderAPI:
        return self._get_canonical_head(self.db)

    @classmethod
    def _get_canonical_head(cls, db: DatabaseAPI) -> BlockHeaderAPI:
        canonical_head_hash = cls._get_canonical_head_hash(db)
        return cls._get_block_header_by_hash(db, canonical_head_hash)

    @classmethod
    def _get_canonical_head_hash(cls, db: DatabaseAPI) -> Hash32:
        try:
            return Hash32(db[SchemaV1.make_canonical_head_hash_lookup_key()])
        except KeyError:
            raise CanonicalHeadNotFound("No canonical head set for this chain")

    #
    # Header API
    #
    def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeaderAPI:
        return self._get_block_header_by_hash(self.db, block_hash)

    @staticmethod
    def _get_block_header_by_hash(db: DatabaseAPI, block_hash: Hash32) -> BlockHeaderAPI:
        """
        Returns the requested block header as specified by block hash.

        Raises BlockNotFound if it is not present in the db.
        """
        validate_word(block_hash, title="Block Hash")
        try:
            header_rlp = db[block_hash]
        except KeyError:
            raise HeaderNotFound(f"No header with hash {encode_hex(block_hash)} found")
        return _decode_block_header(header_rlp)

    def get_score(self, block_hash: Hash32) -> int:
        return self._get_score(self.db, block_hash)

    @staticmethod
    def _get_score(db: DatabaseAPI, block_hash: Hash32) -> int:
        try:
            encoded_score = db[SchemaV1.make_block_hash_to_score_lookup_key(block_hash)]
        except KeyError:
            raise HeaderNotFound(f"No header with hash {encode_hex(block_hash)} found")
        return rlp.decode(encoded_score, sedes=rlp.sedes.big_endian_int)

    def header_exists(self, block_hash: Hash32) -> bool:
        return self._header_exists(self.db, block_hash)

    @staticmethod
    def _header_exists(db: DatabaseAPI, block_hash: Hash32) -> bool:
        validate_word(block_hash, title="Block Hash")
        return block_hash in db

    def persist_header(self,
                       header: BlockHeaderAPI
                       ) -> Tuple[Tuple[BlockHeaderAPI, ...], Tuple[BlockHeaderAPI, ...]]:
        return self.persist_header_chain((header,))

    def persist_header_chain(self,
                             headers: Iterable[BlockHeaderAPI],
                             genesis_parent_hash: Hash32 = GENESIS_PARENT_HASH
                             ) -> Tuple[Tuple[BlockHeaderAPI, ...], Tuple[BlockHeaderAPI, ...]]:
        with self.db.atomic_batch() as db:
            return self._persist_header_chain(db, headers, genesis_parent_hash)

    def persist_checkpoint_header(self, header: BlockHeaderAPI, score: int) -> None:
        with self.db.atomic_batch() as db:
            return self._persist_checkpoint_header(db, header, score)

    @classmethod
    def _set_hash_scores_to_db(
            cls,
            db: DatabaseAPI,
            header: BlockHeaderAPI,
            score: int
    ) -> int:
        new_score = score + header.difficulty

        db.set(
            SchemaV1.make_block_hash_to_score_lookup_key(header.hash),
            rlp.encode(new_score, sedes=rlp.sedes.big_endian_int),
        )

        return new_score

    @classmethod
    def _persist_checkpoint_header(
            cls,
            db: DatabaseAPI,
            header: BlockHeaderAPI,
            score: int
    ) -> None:
        db.set(
            header.hash,
            rlp.encode(header),
        )
        previous_score = score - header.difficulty
        cls._set_hash_scores_to_db(db, header, previous_score)
        cls._set_as_canonical_chain_head(db, header, header.parent_hash)

    @classmethod
    def _persist_header_chain(
            cls,
            db: DatabaseAPI,
            headers: Iterable[BlockHeaderAPI],
            genesis_parent_hash: Hash32,
    ) -> Tuple[Tuple[BlockHeaderAPI, ...], Tuple[BlockHeaderAPI, ...]]:
        headers_iterator = iter(headers)

        try:
            first_header = first(headers_iterator)
        except StopIteration:
            return tuple(), tuple()

        is_genesis = first_header.parent_hash == genesis_parent_hash
        if not is_genesis and not cls._header_exists(db, first_header.parent_hash):
            raise ParentNotFound(
                f"Cannot persist block header ({encode_hex(first_header.hash)}) "
                f"with unknown parent ({encode_hex(first_header.parent_hash)})"
            )

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
                    f"Non-contiguous chain. Expected {encode_hex(child.hash)} "
                    f"to have {encode_hex(parent.hash)} as parent "
                    f"but was {encode_hex(child.parent_hash)}"
                )

            curr_chain_head = child
            db.set(
                curr_chain_head.hash,
                rlp.encode(curr_chain_head),
            )

            score = cls._set_hash_scores_to_db(db, curr_chain_head, score)

        try:
            previous_canonical_head = cls._get_canonical_head_hash(db)
            head_score = cls._get_score(db, previous_canonical_head)
        except CanonicalHeadNotFound:
            return cls._set_as_canonical_chain_head(db, curr_chain_head, genesis_parent_hash)

        if score > head_score:
            return cls._set_as_canonical_chain_head(db, curr_chain_head, genesis_parent_hash)

        return tuple(), tuple()

    @classmethod
    def _set_as_canonical_chain_head(
        cls,
        db: DatabaseAPI,
        header: BlockHeaderAPI,
        genesis_parent_hash: Hash32,
    ) -> Tuple[Tuple[BlockHeaderAPI, ...], Tuple[BlockHeaderAPI, ...]]:
        """
        Sets the canonical chain HEAD to the block header as specified by the
        given block hash.

        :return: a tuple of the headers that are newly in the canonical chain, and the headers that
            are no longer in the canonical chain
        """
        try:
            current_canonical_head = cls._get_canonical_head_hash(db)
        except CanonicalHeadNotFound:
            current_canonical_head = None

        new_canonical_headers: Tuple[BlockHeaderAPI, ...]
        old_canonical_headers: Tuple[BlockHeaderAPI, ...]

        if current_canonical_head and header.parent_hash == current_canonical_head:
            # the calls to _find_new_ancestors and _decanonicalize_old_headers are
            # relatively expensive, it's better to skip them in this case, where we're
            # extending the canonical chain by a header
            new_canonical_headers = (header,)
            old_canonical_headers = ()
        else:
            new_canonical_headers = cast(
                Tuple[BlockHeaderAPI, ...],
                tuple(reversed(cls._find_new_ancestors(db, header, genesis_parent_hash)))
            )
            old_canonical_headers = cls._decanonicalize_old_headers(
                db, new_canonical_headers
            )

        for h in new_canonical_headers:
            cls._add_block_number_to_hash_lookup(db, h)

        db.set(SchemaV1.make_canonical_head_hash_lookup_key(), header.hash)

        return new_canonical_headers, old_canonical_headers

    @classmethod
    def _decanonicalize_old_headers(
        cls,
        db: DatabaseAPI,
        new_canonical_headers: Tuple[BlockHeaderAPI, ...]
    ) -> Tuple[BlockHeaderAPI, ...]:
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

        return tuple(old_canonical_headers)

    @classmethod
    @to_tuple
    def _find_new_ancestors(cls,
                            db: DatabaseAPI,
                            header: BlockHeaderAPI,
                            genesis_parent_hash: Hash32) -> Iterable[BlockHeaderAPI]:
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

            if h.parent_hash == genesis_parent_hash:
                break
            else:
                h = cls._get_block_header_by_hash(db, h.parent_hash)

    @staticmethod
    def _add_block_number_to_hash_lookup(db: DatabaseAPI, header: BlockHeaderAPI) -> None:
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


# When performing a chain sync (either fast or regular modes), we'll very often need to look
# up recent block headers to validate the chain, and decoding their RLP representation is
# relatively expensive so we cache that here, but use a small cache because we *should* only
# be looking up recent blocks.
@functools.lru_cache(128)
def _decode_block_header(header_rlp: bytes) -> BlockHeaderAPI:
    return rlp.decode(header_rlp, sedes=BlockHeader)
