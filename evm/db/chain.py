import functools
import itertools

from abc import (
    ABCMeta,
    abstractmethod
)
from typing import (
    Dict,
    Iterable,
    List,
    Tuple,
    Type,
    TYPE_CHECKING,
)

import rlp

from trie import (
    HexaryTrie,
)

from eth_utils import (
    to_list,
    to_tuple,
)

from eth_hash.auto import keccak

from evm.constants import (
    GENESIS_PARENT_HASH,
)
from evm.exceptions import (
    BlockNotFound,
    CanonicalHeadNotFound,
    ParentNotFound,
    TransactionNotFound,
)
from evm.db.backends.base import (
    BaseDB
)
from evm.rlp.headers import (
    BlockHeader,
)
from evm.rlp.receipts import (
    Receipt
)
from evm.utils.db import (
    make_block_hash_to_score_lookup_key,
    make_block_number_to_hash_lookup_key,
    make_transaction_hash_to_block_lookup_key,
)
from evm.utils.hexadecimal import (
    encode_hex,
)
from evm.validation import (
    validate_uint256,
    validate_word,
)

if TYPE_CHECKING:
    from evm.rlp.blocks import (  # noqa: F401
        BaseBlock
    )
    from evm.rlp.transactions import (  # noqa: F401
        BaseTransaction
    )

CANONICAL_HEAD_HASH_DB_KEY = b'v1:canonical_head_hash'


class TransactionKey(rlp.Serializable):
    fields = [
        ('block_number', rlp.sedes.big_endian_int),
        ('index', rlp.sedes.big_endian_int),
    ]


class BaseChainDB(metaclass=ABCMeta):
    #
    # Trie
    #
    def __init__(self,
                 db: BaseDB) -> None:

        self.db = db

    #
    # Canonical chain API
    #
    @abstractmethod
    def get_canonical_head(self) -> BlockHeader:
        """
        Returns the current block header at the head of the chain.
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

    #
    # Block Header API
    #
    @abstractmethod
    def get_block_header_by_hash(self, block_hash: bytes) -> BlockHeader:
        """
        Returns the requested block header as specified by block hash.

        Raises BlockNotFound if it is not present in the db.
        """
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def header_exists(self, block_hash: bytes) -> bool:
        """
        Returns True if the header with the given block hash is in our DB.
        """
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def persist_header(self, header: BlockHeader) -> Tuple[BlockHeader, ...]:
        """
        :returns: iterable of headers newly on the canonical chain
        """
        raise NotImplementedError("ChainDB classes must implement this method")

    #
    # Block API
    @abstractmethod
    def lookup_block_hash(self, block_number: int) -> bytes:
        """
        Return the block hash for the given block number.
        """
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def get_block_uncles(self, uncles_hash: bytes) -> List[BlockHeader]:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def get_score(self, block_hash: bytes) -> int:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def persist_block(self, block: 'BaseBlock') -> None:
        """
        Chain must do follow-up work to persist transactions to db
        """
        raise NotImplementedError("ChainDB classes must implement this method")

    #
    # Transaction and Receipt API
    #
    @abstractmethod
    def get_receipts(self, header: BlockHeader, receipt_class: Type[Receipt]) -> Iterable[Receipt]:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def get_block_transaction_hashes(self, block_header: BlockHeader) -> Iterable[bytes]:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def get_block_transactions(
            self,
            block_header: BlockHeader,
            transaction_class: Type['BaseTransaction']) -> Iterable['BaseTransaction']:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def get_transaction_by_index(
            self,
            block_number: int,
            transaction_index: int,
            transaction_class: Type['BaseTransaction']) -> Type['BaseTransaction']:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def get_transaction_index(self, transaction_hash: bytes) -> Tuple[int, int]:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def add_transaction(self,
                        block_header: BlockHeader,
                        index_key: int, transaction: 'BaseTransaction') -> bytes:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def add_receipt(self, block_header: BlockHeader, index_key: int, receipt: Receipt) -> bytes:
        raise NotImplementedError("ChainDB classes must implement this method")

    #
    # Raw Database API
    #
    @abstractmethod
    def exists(self, key: bytes) -> bool:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def persist_trie_data_dict(self, trie_data_dict: Dict[bytes, bytes]) -> None:
        """
        Store raw trie data to db from a dict
        """
        raise NotImplementedError("ChainDB classes must implement this method")


class ChainDB(BaseChainDB):
    #
    # Canonical chain API
    #
    def get_canonical_head(self) -> BlockHeader:
        if not self.exists(CANONICAL_HEAD_HASH_DB_KEY):
            raise CanonicalHeadNotFound("No canonical head set for this chain")
        return self.get_block_header_by_hash(self.db.get(CANONICAL_HEAD_HASH_DB_KEY))

    def get_canonical_block_header_by_number(self, block_number: int) -> BlockHeader:
        """
        Returns the block header with the given number in the canonical chain.

        Raises BlockNotFound if there's no block header with the given number in the
        canonical chain.
        """
        validate_uint256(block_number, title="Block Number")
        return self.get_block_header_by_hash(self.lookup_block_hash(block_number))

    #
    # Block Header API
    #
    def get_block_header_by_hash(self, block_hash: bytes) -> BlockHeader:
        """
        Returns the requested block header as specified by block hash.

        Raises BlockNotFound if it is not present in the db.
        """
        validate_word(block_hash, title="Block Hash")
        try:
            header_rlp = self.db.get(block_hash)
        except KeyError:
            raise BlockNotFound("No block with hash {0} found".format(
                encode_hex(block_hash)))
        return _decode_block_header(header_rlp)

    def header_exists(self, block_hash: bytes) -> bool:
        """Returns True if the header with the given block hash is in our DB."""
        return self.db.exists(block_hash)

    # TODO: This method sould take a chain of headers as that's the most common use case
    # and it'd be much faster than inserting each header individually.
    def persist_header(self, header: BlockHeader) -> Tuple[BlockHeader, ...]:
        """
        :returns: iterable of headers newly on the canonical chain
        """
        if header.parent_hash != GENESIS_PARENT_HASH and not self.header_exists(header.parent_hash):
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
            make_block_hash_to_score_lookup_key(header.hash),
            rlp.encode(score, sedes=rlp.sedes.big_endian_int))

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

    def _set_as_canonical_chain_head(self, header: BlockHeader) -> Tuple[BlockHeader, ...]:
        """
        :returns: iterable of headers newly on the canonical head
        """
        try:
            self.get_block_header_by_hash(header.hash)
        except BlockNotFound:
            raise ValueError("Cannot use unknown block hash as canonical head: {}".format(
                header.hash))

        new_canonical_headers = tuple(reversed(self._find_new_ancestors(header)))

        # remove transaction lookups for blocks that are no longer canonical
        for h in new_canonical_headers:
            try:
                old_hash = self.lookup_block_hash(h.block_number)
            except KeyError:
                # no old block, and no more possible
                break
            else:
                old_header = self.get_block_header_by_hash(old_hash)
                for transaction_hash in self.get_block_transaction_hashes(old_header):
                    self._remove_transaction_from_canonical_chain(transaction_hash)
                    # TODO re-add txn to internal pending pool (only if local sender)
                    pass

        for h in new_canonical_headers:
            self._add_block_number_to_hash_lookup(h)

        self.db.set(CANONICAL_HEAD_HASH_DB_KEY, header.hash)

        return new_canonical_headers

    @to_tuple
    def _find_new_ancestors(self, header: BlockHeader) -> Iterable[BlockHeader]:
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
                orig = self.get_canonical_block_header_by_number(h.block_number)
            except KeyError:
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
                h = self.get_block_header_by_hash(h.parent_hash)

    def _add_block_number_to_hash_lookup(self, header: BlockHeader) -> None:
        block_number_to_hash_key = make_block_number_to_hash_lookup_key(
            header.block_number
        )
        self.db.set(
            block_number_to_hash_key,
            rlp.encode(header.hash, sedes=rlp.sedes.binary),
        )

    #
    # Block API
    #
    def get_score(self, block_hash: bytes) -> int:
        return rlp.decode(
            self.db.get(make_block_hash_to_score_lookup_key(block_hash)),
            sedes=rlp.sedes.big_endian_int)

    def lookup_block_hash(self, block_number: int) -> bytes:
        """
        Return the block hash for the given block number.
        """
        validate_uint256(block_number, title="Block Number")
        number_to_hash_key = make_block_number_to_hash_lookup_key(block_number)
        return rlp.decode(
            self.db.get(number_to_hash_key),
            sedes=rlp.sedes.binary,
        )

    def persist_block(self, block: 'BaseBlock') -> None:
        '''Persist the given block's header and uncles.

        Assumes all block transactions have been persisted already.
        '''
        new_canonical_headers = self.persist_header(block.header)

        for header in new_canonical_headers:
            for index, transaction_hash in enumerate(self.get_block_transaction_hashes(header)):
                self._add_transaction_to_canonical_chain(transaction_hash, header, index)

        if hasattr(block, "uncles"):
            uncles_hash = self.persist_uncles(block.uncles)
            assert uncles_hash == block.header.uncles_hash

    def persist_uncles(self, uncles: Tuple) -> bytes:
        uncles_hash = keccak(rlp.encode(uncles))
        self.db.set(
            uncles_hash,
            rlp.encode(uncles, sedes=rlp.sedes.CountableList(BlockHeader)))
        return uncles_hash

    def get_block_uncles(self, uncles_hash: bytes) -> List[BlockHeader]:
        validate_word(uncles_hash, title="Uncles Hash")
        return rlp.decode(self.db.get(uncles_hash), sedes=rlp.sedes.CountableList(BlockHeader))

    #
    # Transaction and Receipt API
    #
    @to_list
    def get_receipts(self, header: BlockHeader, receipt_class: Type[Receipt]) -> Iterable[Receipt]:
        receipt_db = HexaryTrie(db=self.db, root_hash=header.receipt_root)
        for receipt_idx in itertools.count():
            receipt_key = rlp.encode(receipt_idx)
            if receipt_key in receipt_db:
                receipt_data = receipt_db[receipt_key]
                yield rlp.decode(receipt_data, sedes=receipt_class)
            else:
                break

    def _get_block_transaction_data(self, transaction_root: bytes) -> Iterable[bytes]:
        '''
        :returns: iterable of encoded transactions for the given block header
        '''
        transaction_db = HexaryTrie(self.db, root_hash=transaction_root)
        for transaction_idx in itertools.count():
            transaction_key = rlp.encode(transaction_idx)
            if transaction_key in transaction_db:
                yield transaction_db[transaction_key]
            else:
                break

    @to_list
    def get_block_transaction_hashes(self, block_header: BlockHeader) -> Iterable[bytes]:
        for encoded_transaction in self._get_block_transaction_data(block_header.transaction_root):
            yield keccak(encoded_transaction)

    def get_block_transactions(
            self,
            header: BlockHeader,
            transaction_class: Type['BaseTransaction']) -> Iterable['BaseTransaction']:
        return self._get_block_transactions(header.transaction_root, transaction_class)

    @functools.lru_cache(maxsize=32)
    @to_list
    def _get_block_transactions(
            self,
            transaction_root: bytes,
            transaction_class: Type['BaseTransaction']) -> Iterable['BaseTransaction']:
        for encoded_transaction in self._get_block_transaction_data(transaction_root):
            yield rlp.decode(encoded_transaction, sedes=transaction_class)

    def get_transaction_by_index(
            self,
            block_number: int,
            transaction_index: int,
            transaction_class: Type['BaseTransaction']) -> Type['BaseTransaction']:
        try:
            block_header = self.get_canonical_block_header_by_number(block_number)
        except KeyError:
            raise TransactionNotFound("Block {} is not in the canonical chain".format(block_number))
        transaction_db = HexaryTrie(self.db, root_hash=block_header.transaction_root)
        encoded_index = rlp.encode(transaction_index)
        if encoded_index in transaction_db:
            encoded_transaction = transaction_db[encoded_index]
            return rlp.decode(encoded_transaction, sedes=transaction_class)
        else:
            raise TransactionNotFound(
                "No transaction is at index {} of block {}".format(transaction_index, block_number))

    def get_transaction_index(self, transaction_hash: bytes) -> Tuple[int, int]:
        try:
            encoded_key = self.db.get(make_transaction_hash_to_block_lookup_key(transaction_hash))
        except KeyError:
            raise TransactionNotFound(
                "Transaction {} not found in canonical chain".format(encode_hex(transaction_hash)))

        transaction_key = rlp.decode(encoded_key, sedes=TransactionKey)
        return (transaction_key.block_number, transaction_key.index)

    def _remove_transaction_from_canonical_chain(self, transaction_hash: bytes) -> None:
        self.db.delete(make_transaction_hash_to_block_lookup_key(transaction_hash))

    def _add_transaction_to_canonical_chain(self,
                                            transaction_hash: bytes,
                                            block_header: BlockHeader,
                                            index: int) -> None:
        """
        :param bytes transaction_hash: the hash of the transaction to add the lookup for
        :param block_header: The header of the block with the txn that is in the canonical chain
        :param int index: the position of the transaction in the block
        - add lookup from transaction hash to the block number and index that the body is stored at
        - remove transaction hash to body lookup in the pending pool
        """
        transaction_key = TransactionKey(block_header.block_number, index)
        self.db.set(
            make_transaction_hash_to_block_lookup_key(transaction_hash),
            rlp.encode(transaction_key),
        )

    def add_transaction(self,
                        block_header: BlockHeader,
                        index_key: int,
                        transaction: 'BaseTransaction') -> bytes:
        transaction_db = HexaryTrie(self.db, root_hash=block_header.transaction_root)
        transaction_db[index_key] = rlp.encode(transaction)
        return transaction_db.root_hash

    def add_receipt(self, block_header: BlockHeader, index_key: int, receipt: Receipt) -> bytes:
        receipt_db = HexaryTrie(db=self.db, root_hash=block_header.receipt_root)
        receipt_db[index_key] = rlp.encode(receipt)
        return receipt_db.root_hash

    #
    # Raw Database API
    #
    def exists(self, key: bytes) -> bool:
        return self.db.exists(key)

    def persist_trie_data_dict(self, trie_data_dict: Dict[bytes, bytes]) -> None:
        """
        Store raw trie data to db from a dict
        """
        for key, value in trie_data_dict.items():
            self.db[key] = value


# When performing a chain sync (either fast or regular modes), we'll very often need to look
# up recent block headers to validate the chain, and decoding their RLP representation is
# relatively expensive so we cache that here, but use a small cache because we *should* only
# be looking up recent blocks.
@functools.lru_cache(128)
def _decode_block_header(header_rlp: bytes) -> BlockHeader:
    return rlp.decode(header_rlp, sedes=BlockHeader)


class AsyncChainDB(ChainDB):
    async def coro_get_score(self, *args, **kwargs):
        raise NotImplementedError()

    async def coro_get_block_header_by_hash(self, *args, **kwargs):
        raise NotImplementedError()

    async def coro_get_canonical_head(self, *args, **kwargs):
        raise NotImplementedError()

    async def coro_header_exists(self, *args, **kwargs):
        raise NotImplementedError()

    async def coro_lookup_block_hash(self, *args, **kwargs):
        raise NotImplementedError()

    async def coro_persist_header(self, *args, **kwargs):
        raise NotImplementedError()

    async def coro_persist_uncles(self, *args, **kwargs):
        raise NotImplementedError()

    async def coro_persist_trie_data_dict(self, *args, **kwargs):
        raise NotImplementedError()
