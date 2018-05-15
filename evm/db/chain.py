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

from eth_typing import (
    BlockNumber,
    Hash32
)

from eth_utils import (
    to_list,
    to_tuple,
)

from eth_hash.auto import keccak

from evm.exceptions import (
    HeaderNotFound,
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
    # Uncles API
    #
    @abstractmethod
    def get_block_uncles(self, uncles_hash: Hash32) -> List[BlockHeader]:
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
    def __init__(self, base_db: BaseDB) -> None:
        self.base_db = base_db

    #
    # Uncles API
    #
    def get_block_uncles(self, uncles_hash: Hash32) -> List[BlockHeader]:
        """
        Returns an iterable of uncle headers specified by the given uncles_hash
        """
        validate_word(uncles_hash, title="Uncles Hash")
        try:
            encoded_uncles = self.base_db[uncles_hash]
        except KeyError:
            raise HeaderNotFound(
                "No uncles found for hash {0}".format(uncles_hash)
            )
        else:
            return rlp.decode(encoded_uncles, sedes=rlp.sedes.CountableList(BlockHeader))

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
        self.base_db.set(
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
        receipt_db = HexaryTrie(db=self.base_db, root_hash=block_header.receipt_root)
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
        transaction_db = HexaryTrie(self.base_db, root_hash=block_header.transaction_root)
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
        receipt_db = HexaryTrie(db=self.base_db, root_hash=header.receipt_root)
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
        transaction_db = HexaryTrie(self.base_db, root_hash=block_header.transaction_root)
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
            encoded_key = self.base_db[key]
        except KeyError:
            raise TransactionNotFound(
                "Transaction {} not found in canonical chain".format(encode_hex(transaction_hash)))

        transaction_key = rlp.decode(encoded_key, sedes=TransactionKey)
        return (transaction_key.block_number, transaction_key.index)

    def _get_block_transaction_data(self, transaction_root: Hash32) -> Iterable[Hash32]:
        '''
        Returns iterable of the encoded transactions for the given block header
        '''
        transaction_db = HexaryTrie(self.base_db, root_hash=transaction_root)
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
        self.base_db.delete(SchemaV1.make_transaction_hash_to_block_lookup_key(transaction_hash))

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
        self.base_db.set(
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
        return self.base_db.exists(key)

    def persist_trie_data_dict(self, trie_data_dict: Dict[bytes, bytes]) -> None:
        """
        Store raw trie data to db from a dict
        """
        for key, value in trie_data_dict.items():
            self.base_db[key] = value


# When performing a chain sync (either fast or regular modes), we'll very often need to look
# up recent block headers to validate the chain, and decoding their RLP representation is
# relatively expensive so we cache that here, but use a small cache because we *should* only
# be looking up recent blocks.
@functools.lru_cache(128)
def _decode_block_header(header_rlp: bytes) -> BlockHeader:
    return rlp.decode(header_rlp, sedes=BlockHeader)
