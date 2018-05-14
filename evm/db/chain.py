import functools
import itertools

from abc import (
    ABCMeta,
    abstractmethod
)
from typing import (
    cast,
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

from eth_typing import (
    BlockNumber,
    Hash32
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
    CanonicalHeadNotFound,
    HeaderNotFound,
    ParentNotFound,
    TransactionNotFound,
)
from evm.db.backends.base import (
    BaseDB
)
from evm.db.schema import SchemaV1
from evm.rlp.headers import (
    BlockHeader,
)
from evm.rlp.receipts import (
    Receipt
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


class TransactionKey(rlp.Serializable):
    fields = [
        ('block_number', rlp.sedes.big_endian_int),
        ('index', rlp.sedes.big_endian_int),
    ]


class BaseChainDB(metaclass=ABCMeta):
    db = None  # type: BaseDB

    @abstractmethod
    def __init__(self, db: BaseDB) -> None:
        raise NotImplementedError("ChainDB classes must implement this method")

    #
    # Canonical Chain API
    #
    @abstractmethod
    def get_canonical_block_header_by_number(self, block_number: BlockNumber) -> BlockHeader:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def get_canonical_block_hash(self, block_number: BlockNumber) -> Hash32:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def get_canonical_head(self) -> BlockHeader:
        raise NotImplementedError("ChainDB classes must implement this method")

    #
    # Header API
    #
    @abstractmethod
    def header_exists(self, block_hash: Hash32) -> bool:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def get_block_uncles(self, uncles_hash: Hash32) -> List[BlockHeader]:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def get_score(self, block_hash: Hash32) -> int:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def persist_header(self, header: BlockHeader) -> Tuple[BlockHeader, ...]:
        raise NotImplementedError("ChainDB classes must implement this method")

    #
    # Block API
    #
    @abstractmethod
    def persist_block(self, block: 'BaseBlock') -> None:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def persist_uncles(self, uncles: Tuple[BlockHeader]) -> Hash32:
        raise NotImplementedError("ChainDB classes must implement this method")

    #
    # Transaction API
    #
    @abstractmethod
    def add_receipt(self,
                    block_header: BlockHeader,
                    index_key: int, receipt: Receipt) -> Hash32:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def add_transaction(self,
                        block_header: BlockHeader,
                        index_key: int, transaction: 'BaseTransaction') -> Hash32:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def get_block_transactions(
            self,
            block_header: BlockHeader,
            transaction_class: Type['BaseTransaction']) -> Iterable['BaseTransaction']:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def get_block_transaction_hashes(self, block_header: BlockHeader) -> Iterable[Hash32]:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def get_receipts(self,
                     header: BlockHeader,
                     receipt_class: Type[Receipt]) -> Iterable[Receipt]:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def get_transaction_by_index(
            self,
            block_number: BlockNumber,
            transaction_index: int,
            transaction_class: Type['BaseTransaction']) -> 'BaseTransaction':
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def get_transaction_index(self, transaction_hash: Hash32) -> Tuple[BlockNumber, int]:
        raise NotImplementedError("ChainDB classes must implement this method")

    #
    # Raw Database API
    #
    @abstractmethod
    def exists(self, key: bytes) -> bool:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def persist_trie_data_dict(self, trie_data_dict: Dict[bytes, bytes]) -> None:
        raise NotImplementedError("ChainDB classes must implement this method")


class ChainDB(BaseChainDB):
    def __init__(self, db: BaseDB) -> None:
        self.db = db

    #
    # Canonical Chain API
    #
    def get_canonical_block_hash(self, block_number: BlockNumber) -> Hash32:
        """
        Return the block hash for the given block number.
        """
        validate_uint256(block_number, title="Block Number")
        number_to_hash_key = SchemaV1.make_block_number_to_hash_lookup_key(block_number)
        try:
            return rlp.decode(
                self.db[number_to_hash_key],
                sedes=rlp.sedes.binary,
            )
        except KeyError:
            raise HeaderNotFound(
                "No header found on the canonical chain with number {0}".format(block_number)
            )

    def get_canonical_block_header_by_number(self, block_number: BlockNumber) -> BlockHeader:
        """
        Returns the block header with the given number in the canonical chain.

        Raises HeaderNotFound if there's no block header with the given number in the
        canonical chain.
        """
        validate_uint256(block_number, title="Block Number")
        return self.get_block_header_by_hash(self.get_canonical_block_hash(block_number))

    def get_canonical_head(self) -> BlockHeader:
        """
        Returns the current block header at the head of the chain.

        Raises CanonicalHeadNotFound if no canonical head has been set.
        """
        try:
            canonical_head_hash = self.db[SchemaV1.make_canonical_head_hash_lookup_key()]
        except KeyError:
            raise CanonicalHeadNotFound("No canonical head set for this chain")
        return self.get_block_header_by_hash(
            cast(Hash32, canonical_head_hash),
        )

    #
    # Header API
    #
    def header_exists(self, block_hash: Hash32) -> bool:
        """
        Returns True if the header with the given hash is in our DB.
        """
        return self.db.exists(block_hash)

    def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        """
        Returns the requested block header as specified by block hash.

        Raises HeaderNotFound if it is not present in the db.
        """
        validate_word(block_hash, title="Block Hash")
        try:
            header_rlp = self.db[block_hash]
        except KeyError:
            raise HeaderNotFound(
                "No header with hash {0} found".format(encode_hex(block_hash))
            )
        return _decode_block_header(header_rlp)

    def get_block_uncles(self, uncles_hash: Hash32) -> List[BlockHeader]:
        """
        Returns an iterable of uncle headers specified by the given uncles_hash
        """
        validate_word(uncles_hash, title="Uncles Hash")
        try:
            encoded_uncles = self.db[uncles_hash]
        except KeyError:
            raise HeaderNotFound(
                "No uncles found for hash {0}".format(uncles_hash)
            )
        else:
            return rlp.decode(encoded_uncles, sedes=rlp.sedes.CountableList(BlockHeader))

    def get_score(self, block_hash: Hash32) -> int:
        """
        Returns the score for the header with the given hash.

        Raises HeaderNotFound if no header with the given has is found in the database.
        """
        try:
            encoded_score = self.db[SchemaV1.make_block_hash_to_score_lookup_key(block_hash)]
        except KeyError:
            raise HeaderNotFound(
                "No header with hash {0} found".format(encode_hex(block_hash))
            )
        else:
            return rlp.decode(
                encoded_score,
                sedes=rlp.sedes.big_endian_int,
            )

    # TODO: This method should take a chain of headers as that's the most common use case
    # and it'd be much faster than inserting each header individually.
    def persist_header(self, header: BlockHeader) -> Tuple[BlockHeader, ...]:
        """
        Returns iterable of headers newly on the canonical chain
        """
        is_genesis = header.parent_hash == GENESIS_PARENT_HASH
        if not is_genesis and not self.header_exists(header.parent_hash):
            raise ParentNotFound(
                "Cannot persist block header ({}) with unknown parent ({})".format(
                    encode_hex(header.hash), encode_hex(header.parent_hash)))

        self.db.set(
            header.hash,
            rlp.encode(header),
        )

        if is_genesis:
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

    # TODO: update this to take a `hash` rather than a full header object.
    def _set_as_canonical_chain_head(self, header: BlockHeader) -> Tuple[BlockHeader, ...]:
        """
        Returns iterable of headers newly on the canonical head
        """
        try:
            self.get_block_header_by_hash(header.hash)
        except HeaderNotFound:
            raise ValueError("Cannot use unknown block hash as canonical head: {}".format(
                header.hash))

        new_canonical_headers = tuple(reversed(self._find_new_ancestors(header)))

        # remove transaction lookups for blocks that are no longer canonical
        for h in new_canonical_headers:
            try:
                old_hash = self.get_canonical_block_hash(h.block_number)
            except HeaderNotFound:
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

        self.db.set(SchemaV1.make_canonical_head_hash_lookup_key(), header.hash)

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
                h = self.get_block_header_by_hash(h.parent_hash)

    def _add_block_number_to_hash_lookup(self, header: BlockHeader) -> None:
        """
        Sets a record in the database to allow looking up this header by its
        block number.
        """
        block_number_to_hash_key = SchemaV1.make_block_number_to_hash_lookup_key(
            header.block_number
        )
        self.db.set(
            block_number_to_hash_key,
            rlp.encode(header.hash, sedes=rlp.sedes.binary),
        )

    #
    # Block API
    #
    def persist_block(self, block: 'BaseBlock') -> None:
        '''
        Persist the given block's header and uncles.

        Assumes all block transactions have been persisted already.
        '''
        new_canonical_headers = self.persist_header(block.header)

        for header in new_canonical_headers:
            for index, transaction_hash in enumerate(self.get_block_transaction_hashes(header)):
                self._add_transaction_to_canonical_chain(transaction_hash, header, index)

        if hasattr(block, "uncles"):
            uncles_hash = self.persist_uncles(block.uncles)
            assert uncles_hash == block.header.uncles_hash

    def persist_uncles(self, uncles: Tuple[BlockHeader]) -> Hash32:
        """
        Persists the list of uncles to the database.

        Returns the uncles hash.
        """
        uncles_hash = keccak(rlp.encode(uncles))
        self.db.set(
            uncles_hash,
            rlp.encode(uncles, sedes=rlp.sedes.CountableList(BlockHeader)))
        return uncles_hash

    #
    # Transaction API
    #
    def add_receipt(self, block_header: BlockHeader, index_key: int, receipt: Receipt) -> Hash32:
        """
        Adds the given receipt to the provide block header.

        Returns the updated `receipts_root` for updated block header.
        """
        receipt_db = HexaryTrie(db=self.db, root_hash=block_header.receipt_root)
        receipt_db[index_key] = rlp.encode(receipt)
        return receipt_db.root_hash

    def add_transaction(self,
                        block_header: BlockHeader,
                        index_key: int,
                        transaction: 'BaseTransaction') -> Hash32:
        """
        Adds the given transaction to the provide block header.

        Returns the updated `transactions_root` for updated block header.
        """
        transaction_db = HexaryTrie(self.db, root_hash=block_header.transaction_root)
        transaction_db[index_key] = rlp.encode(transaction)
        return transaction_db.root_hash

    def get_block_transactions(
            self,
            header: BlockHeader,
            transaction_class: Type['BaseTransaction']) -> Iterable['BaseTransaction']:
        """
        Returns an iterable of transactions for the block speficied by the
        given block header.
        """
        return self._get_block_transactions(header.transaction_root, transaction_class)

    @to_list
    def get_block_transaction_hashes(self, block_header: BlockHeader) -> Iterable[Hash32]:
        """
        Returns an iterable of the transaction hashes from th block specified
        by the given block header.
        """
        all_encoded_transactions = self._get_block_transaction_data(
            block_header.transaction_root,
        )
        for encoded_transaction in all_encoded_transactions:
            yield keccak(encoded_transaction)

    @to_tuple
    def get_receipts(self,
                     header: BlockHeader,
                     receipt_class: Type[Receipt]) -> Iterable[Receipt]:
        """
        Returns an iterable of receipts for the block specified by the given
        block header.
        """
        receipt_db = HexaryTrie(db=self.db, root_hash=header.receipt_root)
        for receipt_idx in itertools.count():
            receipt_key = rlp.encode(receipt_idx)
            if receipt_key in receipt_db:
                receipt_data = receipt_db[receipt_key]
                yield rlp.decode(receipt_data, sedes=receipt_class)
            else:
                break

    def get_transaction_by_index(
            self,
            block_number: BlockNumber,
            transaction_index: int,
            transaction_class: Type['BaseTransaction']) -> 'BaseTransaction':
        """
        Returns the transaction at the specified `transaction_index` from the
        block specified by `block_number` from the canonical chain.

        Raises TransactionNotFound if no block
        """
        try:
            block_header = self.get_canonical_block_header_by_number(block_number)
        except HeaderNotFound:
            raise TransactionNotFound("Block {} is not in the canonical chain".format(block_number))
        transaction_db = HexaryTrie(self.db, root_hash=block_header.transaction_root)
        encoded_index = rlp.encode(transaction_index)
        if encoded_index in transaction_db:
            encoded_transaction = transaction_db[encoded_index]
            return rlp.decode(encoded_transaction, sedes=transaction_class)
        else:
            raise TransactionNotFound(
                "No transaction is at index {} of block {}".format(transaction_index, block_number))

    def get_transaction_index(self, transaction_hash: Hash32) -> Tuple[BlockNumber, int]:
        """
        Returns a 2-tuple of (block_number, transaction_index) indicating which
        block the given transaction can be found in and at what index in the
        block transactions.

        Raises TransactionNotFound if the transaction_hash is not found in the
        canonical chain.
        """
        key = SchemaV1.make_transaction_hash_to_block_lookup_key(transaction_hash)
        try:
            encoded_key = self.db[key]
        except KeyError:
            raise TransactionNotFound(
                "Transaction {} not found in canonical chain".format(encode_hex(transaction_hash)))

        transaction_key = rlp.decode(encoded_key, sedes=TransactionKey)
        return (transaction_key.block_number, transaction_key.index)

    def _get_block_transaction_data(self, transaction_root: Hash32) -> Iterable[Hash32]:
        '''
        Returns iterable of the encoded transactions for the given block header
        '''
        transaction_db = HexaryTrie(self.db, root_hash=transaction_root)
        for transaction_idx in itertools.count():
            transaction_key = rlp.encode(transaction_idx)
            if transaction_key in transaction_db:
                yield transaction_db[transaction_key]
            else:
                break

    @functools.lru_cache(maxsize=32)
    @to_list
    def _get_block_transactions(
            self,
            transaction_root: Hash32,
            transaction_class: Type['BaseTransaction']) -> Iterable['BaseTransaction']:
        """
        Memoizable version of `get_block_transactions`
        """
        for encoded_transaction in self._get_block_transaction_data(transaction_root):
            yield rlp.decode(encoded_transaction, sedes=transaction_class)

    def _remove_transaction_from_canonical_chain(self, transaction_hash: Hash32) -> None:
        """
        Removes the transaction specified by the given hash from the canonical
        chain.
        """
        self.db.delete(SchemaV1.make_transaction_hash_to_block_lookup_key(transaction_hash))

    def _add_transaction_to_canonical_chain(self,
                                            transaction_hash: Hash32,
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
            SchemaV1.make_transaction_hash_to_block_lookup_key(transaction_hash),
            rlp.encode(transaction_key),
        )

    #
    # Raw Database API
    #
    def exists(self, key: bytes) -> bool:
        """
        Returns True if the given key exists in the database.
        """
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
    async def coro_get_score(self, block_hash: Hash32) -> int:
        raise NotImplementedError()

    async def coro_get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        raise NotImplementedError()

    async def coro_get_canonical_head(self) -> BlockHeader:
        raise NotImplementedError()

    async def coro_header_exists(self, block_hash: Hash32) -> bool:
        raise NotImplementedError()

    async def coro_get_canonical_block_hash(self, block_number: BlockNumber) -> Hash32:
        raise NotImplementedError()

    async def coro_persist_header(self, header: BlockHeader) -> Tuple[BlockHeader, ...]:
        raise NotImplementedError()

    async def coro_persist_uncles(self, uncles: Tuple[BlockHeader]) -> Hash32:
        raise NotImplementedError()

    async def coro_persist_trie_data_dict(self, trie_data_dict: Dict[bytes, bytes]) -> None:
        raise NotImplementedError()
