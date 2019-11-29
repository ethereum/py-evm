import functools
import itertools

from typing import (
    Dict,
    Iterable,
    Tuple,
    Type,
)

from eth_typing import (
    BlockNumber,
    Hash32
)
from eth_utils import (
    encode_hex,
)

from eth_hash.auto import keccak
from trie.exceptions import (
    MissingTrieNode,
)

from eth.abc import (
    BlockAPI,
    BlockHeaderAPI,
    ChainDatabaseAPI,
    DatabaseAPI,
    AtomicDatabaseAPI,
    ReceiptAPI,
    SignedTransactionAPI,
)
from eth.constants import (
    EMPTY_UNCLE_HASH,
    GENESIS_PARENT_HASH,
)
from eth.exceptions import (
    HeaderNotFound,
    ReceiptNotFound,
    TransactionNotFound,
)
from eth.db.header import HeaderDB
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
        to_tuple,
        ValidationError,
    )


class TransactionKey(rlp.Serializable):
    fields = [
        ('block_number', rlp.sedes.big_endian_int),
        ('index', rlp.sedes.big_endian_int),
    ]


class ChainDB(HeaderDB, ChainDatabaseAPI):
    def __init__(self, db: AtomicDatabaseAPI) -> None:
        self.db = db

    #
    # Header API
    #
    def get_block_uncles(self, uncles_hash: Hash32) -> Tuple[BlockHeaderAPI, ...]:
        validate_word(uncles_hash, title="Uncles Hash")
        if uncles_hash == EMPTY_UNCLE_HASH:
            return ()
        try:
            encoded_uncles = self.db[uncles_hash]
        except KeyError:
            raise HeaderNotFound(
                f"No uncles found for hash {uncles_hash}"
            )
        else:
            return tuple(rlp.decode(encoded_uncles, sedes=rlp.sedes.CountableList(BlockHeader)))

    @classmethod
    def _decanonicalize_old_headers(
        cls,
        db: DatabaseAPI,
        new_canonical_headers: Tuple[BlockHeaderAPI, ...]
    ) -> Tuple[BlockHeaderAPI, ...]:
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
                try:
                    transaction_hashes = cls._get_block_transaction_hashes(db, old_header)
                    for transaction_hash in transaction_hashes:
                        cls._remove_transaction_from_canonical_chain(db, transaction_hash)
                except MissingTrieNode:
                    # If the transactions were never stored for the (now) non-canonical
                    # chain, then you don't need to remove them from the canonical chain
                    # lookup.
                    pass

        return tuple(old_canonical_headers)

    #
    # Block API
    #
    def persist_block(self,
                      block: BlockAPI,
                      genesis_parent_hash: Hash32 = GENESIS_PARENT_HASH
                      ) -> Tuple[Tuple[Hash32, ...], Tuple[Hash32, ...]]:
        with self.db.atomic_batch() as db:
            return self._persist_block(db, block, genesis_parent_hash)

    @classmethod
    def _persist_block(
            cls,
            db: DatabaseAPI,
            block: BlockAPI,
            genesis_parent_hash: Hash32) -> Tuple[Tuple[Hash32, ...], Tuple[Hash32, ...]]:
        header_chain = (block.header, )
        new_canonical_headers, old_canonical_headers = cls._persist_header_chain(
            db,
            header_chain,
            genesis_parent_hash
        )

        for header in new_canonical_headers:
            if header.hash == block.hash:
                # Most of the time this is called to persist a block whose parent is the current
                # head, so we optimize for that and read the tx hashes from the block itself. This
                # is specially important during a fast sync.
                tx_hashes = tuple(tx.hash for tx in block.transactions)
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

    def persist_uncles(self, uncles: Tuple[BlockHeaderAPI]) -> Hash32:
        return self._persist_uncles(self.db, uncles)

    @staticmethod
    def _persist_uncles(db: DatabaseAPI, uncles: Tuple[BlockHeaderAPI]) -> Hash32:
        uncles_hash = keccak(rlp.encode(uncles))
        db.set(
            uncles_hash,
            rlp.encode(uncles, sedes=rlp.sedes.CountableList(BlockHeader)))
        return uncles_hash

    #
    # Transaction API
    #
    def add_receipt(self,
                    block_header: BlockHeaderAPI,
                    index_key: int, receipt: ReceiptAPI) -> Hash32:
        receipt_db = HexaryTrie(db=self.db, root_hash=block_header.receipt_root)
        receipt_db[index_key] = rlp.encode(receipt)
        return receipt_db.root_hash

    def add_transaction(self,
                        block_header: BlockHeaderAPI,
                        index_key: int,
                        transaction: SignedTransactionAPI) -> Hash32:
        transaction_db = HexaryTrie(self.db, root_hash=block_header.transaction_root)
        transaction_db[index_key] = rlp.encode(transaction)
        return transaction_db.root_hash

    def get_block_transactions(
            self,
            header: BlockHeaderAPI,
            transaction_class: Type[SignedTransactionAPI]) -> Tuple[SignedTransactionAPI, ...]:
        return self._get_block_transactions(header.transaction_root, transaction_class)

    def get_block_transaction_hashes(self, block_header: BlockHeaderAPI) -> Tuple[Hash32, ...]:
        """
        Returns an iterable of the transaction hashes from the block specified
        by the given block header.
        """
        return self._get_block_transaction_hashes(self.db, block_header)

    @classmethod
    @to_tuple
    def _get_block_transaction_hashes(
            cls,
            db: DatabaseAPI,
            block_header: BlockHeaderAPI) -> Iterable[Hash32]:
        all_encoded_transactions = cls._get_block_transaction_data(
            db,
            block_header.transaction_root,
        )
        for encoded_transaction in all_encoded_transactions:
            yield keccak(encoded_transaction)

    @to_tuple
    def get_receipts(self,
                     header: BlockHeaderAPI,
                     receipt_class: Type[ReceiptAPI]) -> Iterable[ReceiptAPI]:
        receipt_db = HexaryTrie(db=self.db, root_hash=header.receipt_root)
        for receipt_idx in itertools.count():
            receipt_key = rlp.encode(receipt_idx)
            receipt_data = receipt_db[receipt_key]
            if receipt_data != b'':
                yield rlp.decode(receipt_data, sedes=receipt_class)
            else:
                break

    def get_transaction_by_index(
            self,
            block_number: BlockNumber,
            transaction_index: int,
            transaction_class: Type[SignedTransactionAPI]) -> SignedTransactionAPI:
        try:
            block_header = self.get_canonical_block_header_by_number(block_number)
        except HeaderNotFound:
            raise TransactionNotFound(f"Block {block_number} is not in the canonical chain")
        transaction_db = HexaryTrie(self.db, root_hash=block_header.transaction_root)
        encoded_index = rlp.encode(transaction_index)
        encoded_transaction = transaction_db[encoded_index]
        if encoded_transaction != b'':
            return rlp.decode(encoded_transaction, sedes=transaction_class)
        else:
            raise TransactionNotFound(
                f"No transaction is at index {transaction_index} of block {block_number}"
            )

    def get_transaction_index(self, transaction_hash: Hash32) -> Tuple[BlockNumber, int]:
        key = SchemaV1.make_transaction_hash_to_block_lookup_key(transaction_hash)
        try:
            encoded_key = self.db[key]
        except KeyError:
            raise TransactionNotFound(
                f"Transaction {encode_hex(transaction_hash)} not found in canonical chain"
            )

        transaction_key = rlp.decode(encoded_key, sedes=TransactionKey)
        return (transaction_key.block_number, transaction_key.index)

    def get_receipt_by_index(self,
                             block_number: BlockNumber,
                             receipt_index: int) -> ReceiptAPI:
        try:
            block_header = self.get_canonical_block_header_by_number(block_number)
        except HeaderNotFound:
            raise ReceiptNotFound(f"Block {block_number} is not in the canonical chain")

        receipt_db = HexaryTrie(db=self.db, root_hash=block_header.receipt_root)
        receipt_key = rlp.encode(receipt_index)
        receipt_data = receipt_db[receipt_key]
        if receipt_data != b'':
            return rlp.decode(receipt_data, sedes=Receipt)
        else:
            raise ReceiptNotFound(
                f"Receipt with index {receipt_index} not found in block"
            )

    @staticmethod
    def _get_block_transaction_data(db: DatabaseAPI, transaction_root: Hash32) -> Iterable[Hash32]:
        """
        Returns iterable of the encoded transactions for the given block header
        """
        transaction_db = HexaryTrie(db, root_hash=transaction_root)
        for transaction_idx in itertools.count():
            transaction_key = rlp.encode(transaction_idx)
            encoded = transaction_db[transaction_key]
            if encoded != b'':
                yield encoded
            else:
                break

    @functools.lru_cache(maxsize=32)
    @to_tuple
    def _get_block_transactions(
            self,
            transaction_root: Hash32,
            transaction_class: Type[SignedTransactionAPI]) -> Iterable[SignedTransactionAPI]:
        """
        Memoizable version of `get_block_transactions`
        """
        for encoded_transaction in self._get_block_transaction_data(self.db, transaction_root):
            yield rlp.decode(encoded_transaction, sedes=transaction_class)

    @staticmethod
    def _remove_transaction_from_canonical_chain(db: DatabaseAPI, transaction_hash: Hash32) -> None:
        """
        Removes the transaction specified by the given hash from the canonical
        chain.
        """
        db.delete(SchemaV1.make_transaction_hash_to_block_lookup_key(transaction_hash))

    @staticmethod
    def _add_transaction_to_canonical_chain(db: DatabaseAPI,
                                            transaction_hash: Hash32,
                                            block_header: BlockHeaderAPI,
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
        return self.db.exists(key)

    def get(self, key: bytes) -> bytes:
        return self.db[key]

    def persist_trie_data_dict(self, trie_data_dict: Dict[Hash32, bytes]) -> None:
        with self.db.atomic_batch() as db:
            for key, value in trie_data_dict.items():
                db[key] = value
