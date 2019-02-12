import functools
import itertools

from abc import (
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

from eth_typing import (
    BlockNumber,
    Hash32
)
from eth_utils import (
    encode_hex,
)

from eth_hash.auto import keccak

from eth.constants import (
    EMPTY_UNCLE_HASH,
)
from eth.exceptions import (
    HeaderNotFound,
    ReceiptNotFound,
    TransactionNotFound,
)
from eth.db.header import BaseHeaderDB, HeaderDB
from eth.db.backends.base import (
    BaseAtomicDB,
    BaseDB,
)
from eth.db.schema import SchemaV1
from eth.rlp.headers import (
    BlockHeader,
)
from eth.rlp.receipts import (
    Receipt
)
from eth.validation import (
    validate_word,
)
from eth._warnings import catch_and_ignore_import_warning
with catch_and_ignore_import_warning():
    import rlp
    from trie import (
        HexaryTrie,
    )
    from eth_utils import (
        to_list,
        to_tuple,
        ValidationError,
    )

if TYPE_CHECKING:
    from eth.rlp.blocks import (  # noqa: F401
        BaseBlock,
        BaseTransaction
    )


class TransactionKey(rlp.Serializable):
    fields = [
        ('block_number', rlp.sedes.big_endian_int),
        ('index', rlp.sedes.big_endian_int),
    ]


class BaseChainDB(BaseHeaderDB):
    db = None  # type: BaseAtomicDB

    @abstractmethod
    def __init__(self, db: BaseAtomicDB) -> None:
        raise NotImplementedError("ChainDB classes must implement this method")

    #
    # Header API
    #
    @abstractmethod
    def get_block_uncles(self, uncles_hash: Hash32) -> List[BlockHeader]:
        raise NotImplementedError("ChainDB classes must implement this method")

    #
    # Block API
    #
    @abstractmethod
    def persist_block(self,
                      block: 'BaseBlock'
                      ) -> Tuple[Tuple[Hash32, ...], Tuple[Hash32, ...]]:
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
    def get_receipt_by_index(self,
                             block_number: BlockNumber,
                             receipt_index: int) -> Receipt:
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
    def get(self, key: bytes) -> bytes:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    def persist_trie_data_dict(self, trie_data_dict: Dict[Hash32, bytes]) -> None:
        raise NotImplementedError("ChainDB classes must implement this method")


class ChainDB(HeaderDB, BaseChainDB):
    def __init__(self, db: BaseAtomicDB) -> None:
        self.db = db

    #
    # Header API
    #
    def get_block_uncles(self, uncles_hash: Hash32) -> List[BlockHeader]:
        """
        Returns an iterable of uncle headers specified by the given uncles_hash
        """
        validate_word(uncles_hash, title="Uncles Hash")
        if uncles_hash == EMPTY_UNCLE_HASH:
            return []
        try:
            encoded_uncles = self.db[uncles_hash]
        except KeyError:
            raise HeaderNotFound(
                "No uncles found for hash {0}".format(uncles_hash)
            )
        else:
            return rlp.decode(encoded_uncles, sedes=rlp.sedes.CountableList(BlockHeader))

    @classmethod
    def _set_as_canonical_chain_head(cls,
                                     db: BaseDB,
                                     block_hash: Hash32,
                                     ) -> Tuple[Tuple[BlockHeader, ...], Tuple[BlockHeader, ...]]:
        try:
            header = cls._get_block_header_by_hash(db, block_hash)
        except HeaderNotFound:
            raise ValueError("Cannot use unknown block hash as canonical head: {}".format(
                header.hash))

        new_canonical_headers = tuple(reversed(cls._find_new_ancestors(db, header)))
        old_canonical_headers = []

        # remove transaction lookups for blocks that are no longer canonical
        for h in new_canonical_headers:
            try:
                old_hash = cls._get_canonical_block_hash(db, h.block_number)
            except HeaderNotFound:
                # no old block, and no more possible
                break
            else:
                old_header = cls._get_block_header_by_hash(db, old_hash)
                old_canonical_headers.append(old_header)
                for transaction_hash in cls._get_block_transaction_hashes(db, old_header):
                    cls._remove_transaction_from_canonical_chain(db, transaction_hash)

        for h in new_canonical_headers:
            cls._add_block_number_to_hash_lookup(db, h)

        db.set(SchemaV1.make_canonical_head_hash_lookup_key(), header.hash)

        return new_canonical_headers, tuple(old_canonical_headers)

    #
    # Block API
    #
    def persist_block(self,
                      block: 'BaseBlock'
                      ) -> Tuple[Tuple[Hash32, ...], Tuple[Hash32, ...]]:
        """
        Persist the given block's header and uncles.

        Assumes all block transactions have been persisted already.
        """
        with self.db.atomic_batch() as db:
            return self._persist_block(db, block)

    @classmethod
    def _persist_block(
            cls,
            db: 'BaseDB',
            block: 'BaseBlock') -> Tuple[Tuple[Hash32, ...], Tuple[Hash32, ...]]:
        header_chain = (block.header, )
        new_canonical_headers, old_canonical_headers = cls._persist_header_chain(db, header_chain)

        for header in new_canonical_headers:
            if header.hash == block.hash:
                # Most of the time this is called to persist a block whose parent is the current
                # head, so we optimize for that and read the tx hashes from the block itself. This
                # is specially important during a fast sync.
                tx_hashes = [tx.hash for tx in block.transactions]
            else:
                tx_hashes = cls._get_block_transaction_hashes(db, header)

            for index, transaction_hash in enumerate(tx_hashes):
                cls._add_transaction_to_canonical_chain(db, transaction_hash, header, index)

        if block.uncles:
            uncles_hash = cls._persist_uncles(db, block.uncles)
        else:
            uncles_hash = EMPTY_UNCLE_HASH
        if uncles_hash != block.header.uncles_hash:
            raise ValidationError(
                "Block's uncles_hash (%s) does not match actual uncles' hash (%s)",
                block.header.uncles_hash, uncles_hash)
        new_canonical_hashes = tuple(header.hash for header in new_canonical_headers)
        old_canonical_hashes = tuple(
            header.hash for header in old_canonical_headers)

        return new_canonical_hashes, old_canonical_hashes

    def persist_uncles(self, uncles: Tuple[BlockHeader]) -> Hash32:
        """
        Persists the list of uncles to the database.

        Returns the uncles hash.
        """
        return self._persist_uncles(self.db, uncles)

    @staticmethod
    def _persist_uncles(db: BaseDB, uncles: Tuple[BlockHeader]) -> Hash32:
        uncles_hash = keccak(rlp.encode(uncles))
        db.set(
            uncles_hash,
            rlp.encode(uncles, sedes=rlp.sedes.CountableList(BlockHeader)))
        return uncles_hash

    #
    # Transaction API
    #
    def add_receipt(self, block_header: BlockHeader, index_key: int, receipt: Receipt) -> Hash32:
        """
        Adds the given receipt to the provided block header.

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
        Adds the given transaction to the provided block header.

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

    def get_block_transaction_hashes(self, block_header: BlockHeader) -> Iterable[Hash32]:
        """
        Returns an iterable of the transaction hashes from the block specified
        by the given block header.
        """
        return self._get_block_transaction_hashes(self.db, block_header)

    @classmethod
    @to_list
    def _get_block_transaction_hashes(
            cls,
            db: BaseDB,
            block_header: BlockHeader) -> Iterable[Hash32]:
        all_encoded_transactions = cls._get_block_transaction_data(
            db,
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

    def get_receipt_by_index(self,
                             block_number: BlockNumber,
                             receipt_index: int) -> Receipt:
        """
        Returns the Receipt of the transaction at specified index
        for the block header obtained by the specified block number
        """
        try:
            block_header = self.get_canonical_block_header_by_number(block_number)
        except HeaderNotFound:
            raise ReceiptNotFound("Block {} is not in the canonical chain".format(block_number))

        receipt_db = HexaryTrie(db=self.db, root_hash=block_header.receipt_root)
        receipt_key = rlp.encode(receipt_index)
        if receipt_key in receipt_db:
            receipt_data = receipt_db[receipt_key]
            return rlp.decode(receipt_data, sedes=Receipt)
        else:
            raise ReceiptNotFound(
                "Receipt with index {} not found in block".format(receipt_index))

    @staticmethod
    def _get_block_transaction_data(db: BaseDB, transaction_root: Hash32) -> Iterable[Hash32]:
        """
        Returns iterable of the encoded transactions for the given block header
        """
        transaction_db = HexaryTrie(db, root_hash=transaction_root)
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
        for encoded_transaction in self._get_block_transaction_data(self.db, transaction_root):
            yield rlp.decode(encoded_transaction, sedes=transaction_class)

    @staticmethod
    def _remove_transaction_from_canonical_chain(db: BaseDB, transaction_hash: Hash32) -> None:
        """
        Removes the transaction specified by the given hash from the canonical
        chain.
        """
        db.delete(SchemaV1.make_transaction_hash_to_block_lookup_key(transaction_hash))

    @staticmethod
    def _add_transaction_to_canonical_chain(db: BaseDB,
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
        db.set(
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

    def get(self, key: bytes) -> bytes:
        """
        Return the value for the given key or a KeyError if it doesn't exist in the database.
        """
        return self.db[key]

    def persist_trie_data_dict(self, trie_data_dict: Dict[Hash32, bytes]) -> None:
        """
        Store raw trie data to db from a dict
        """
        with self.db.atomic_batch() as db:
            for key, value in trie_data_dict.items():
                db[key] = value
