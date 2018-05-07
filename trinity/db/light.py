from abc import ABCMeta, abstractmethod
from typing import Tuple

import rlp

from eth_utils import (
    encode_hex,
)

from evm.constants import (
    GENESIS_PARENT_HASH,
)
from eth.validation import (
    validate_block_number,
    validate_word,
)

from eth_typing import Hash32

from evm.exceptions import (
    CanonicalHeadNotFound,
    HeaderNotFound,
    ParentNotFound,
)
from evm.db import BaseDB
from evm.db.schema import SchemaV1
from evm.rlp.headers import BlockHeader


class BaseLightDB(metaclass=ABCMeta):
    db: BaseDB = None

    def __init__(self, db: BaseDB) -> None:
        self.db = db

    @abstractmethod
    def get_canonical_head(self) -> BlockHeader:
        """
        Returns the current block header at the head of the chain.
        """
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def get_canonical_block_hash(self, block_number: int) -> Hash32:
        """
        Returns the block hash for the canonical block at the given number.

        Raises BlockNotFound if there's no block header with the given number in the
        canonical chain.
        """
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def get_canonical_block_header_by_number(self, block_number: int) -> BlockHeader:
        """
        Returns the block header with the given number in the canonical chain.

        Raises BlockNotFound if there's no block header with the given number in the
        canonical chain.
        """
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        """
        Returns the requested block header as specified by block hash.

        Raises BlockNotFound if it is not present in the db.
        """
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def get_score(self, block_hash: Hash32) -> int:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def perist_header(self, header: BlockHeader) -> None:
        raise NotImplementedError("ChainDB classes must implement this method")


class LightDB(BaseLightDB):
    def get_canonical_head(self) -> BlockHeader:
        """
        Returns the current block header at the head of the chain.
        """
        try:
            canonical_head_hash = self.db[SchemaV1.make_canonical_head_hash_lookup_key()]
        except KeyError:
            raise CanonicalHeadNotFound("No canonical head set for this chain")
        return self.get_block_header_by_hash(canonical_head_hash)

    def get_canonical_block_hash(self, block_number: int) -> Hash32:
        """
        Returns the block hash for the canonical block at the given number.

        Raises BlockNotFound if there's no block header with the given number in the
        canonical chain.
        """
        validate_block_number(block_number, title="Block Number")
        number_to_hash_key = SchemaV1.make_block_number_to_hash_lookup_key(block_number)
        return rlp.decode(
            self.db.get(number_to_hash_key),
            sedes=rlp.sedes.binary,
        )

    def get_canonical_block_header_by_number(self, block_number: int) -> BlockHeader:
        """
        Returns the block header with the given number in the canonical chain.

        Raises BlockNotFound if there's no block header with the given number in the
        canonical chain.
        """
        validate_block_number(block_number, title="Block Number")
        return self.get_block_header_by_hash(self.get_canonical_block_hash(block_number))

    def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        """
        Returns the requested block header as specified by block hash.

        Raises BlockNotFound if it is not present in the db.
        """
        validate_word(block_hash, title="Block Hash")
        try:
            header_rlp = self.db.get(block_hash)
        except KeyError:
            raise HeaderNotFound("No header with hash {0} found".format(
                encode_hex(block_hash)))
        return rlp.decode(header_rlp, BlockHeader)

    def get_score(self, block_hash: Hash32) -> int:
        return rlp.decode(
            self.db.get(SchemaV1.make_block_hash_to_score_lookup_key(block_hash)),
            sedes=rlp.sedes.big_endian_int,
        )

    def persist_header(self, header: BlockHeader) -> Tuple[BlockHeader, ...]:
        """
        :returns: iterable of headers newly on the canonical chain
        """
        if header.parent_hash != GENESIS_PARENT_HASH:
            try:
                self.get_block_header_by_hash(header.parent_hash)
            except HeaderNotFound:
                raise ParentNotFound(
                    "Cannot persist block header ({}) with unknown parent ({})".format(
                        encode_hex(header.hash), encode_hex(header.parent_hash)))

        self.db.set(
            header.hash,
            rlp.encode(header),
        )

        if header.parent_hash == GENESIS_PARENT_HASH:
            score = header.difficulty
        else:
            score = self.get_score(header.parent_hash) + header.difficulty

        self.db.set(
            SchemaV1.make_block_hash_to_score_lookup_key(header.hash),
            rlp.encode(score, sedes=rlp.sedes.big_endian_int),
        )

        try:
            head_score = self.get_score(self.get_canonical_head().hash)
        except CanonicalHeadNotFound:
            new_headers = self._set_as_canonical_chain_head(header)
        else:
            if score > head_score:
                new_headers = self._set_as_canonical_chain_head(header)
            else:
                new_headers = tuple()

        return new_headers
