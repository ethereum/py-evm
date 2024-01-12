import functools
import itertools
from typing import (
    Dict,
    Iterable,
    Sequence,
    Tuple,
    Type,
    cast,
)

from eth_hash.auto import (
    keccak,
)
from eth_typing import (
    BlockNumber,
    Hash32,
)
from eth_utils import (
    encode_hex,
)
from trie.exceptions import (
    MissingTrieNode,
)

from eth._warnings import (
    catch_and_ignore_import_warning,
)
from eth.abc import (
    AtomicDatabaseAPI,
    BlockAPI,
    BlockHeaderAPI,
    ChainDatabaseAPI,
    DatabaseAPI,
    ReceiptAPI,
    ReceiptDecoderAPI,
    SignedTransactionAPI,
    TransactionDecoderAPI,
    WithdrawalAPI,
)
from eth.constants import (
    EMPTY_UNCLE_HASH,
    GENESIS_PARENT_HASH,
)
from eth.db.chain_gaps import (
    GENESIS_CHAIN_GAPS,
    GapChange,
    GapInfo,
    fill_gap,
    is_block_number_in_gap,
    reopen_gap,
)
from eth.db.header import (
    HeaderDB,
)
from eth.db.schema import (
    SchemaV1,
)
from eth.db.trie import (
    make_trie_root_and_nodes,
)
from eth.exceptions import (
    HeaderNotFound,
    ReceiptNotFound,
    TransactionNotFound,
)
from eth.rlp.sedes import (
    chain_gaps,
)
from eth.typing import (
    ChainGaps,
)
from eth.validation import (
    validate_word,
)
from eth.vm.forks.shanghai.withdrawals import (
    Withdrawal,
)
from eth.vm.header import (
    HeaderSedes,
)

with catch_and_ignore_import_warning():
    from eth_utils import (
        ValidationError,
        to_tuple,
    )
    import rlp
    from trie import (
        HexaryTrie,
    )


class BlockDataKey(rlp.Serializable):
    # used for transactions and withdrawals
    fields = [
        ("block_number", rlp.sedes.big_endian_int),
        ("index", rlp.sedes.big_endian_int),
    ]


class ChainDB(HeaderDB, ChainDatabaseAPI):
    def __init__(self, db: AtomicDatabaseAPI) -> None:
        self.db = db

    def get_chain_gaps(self) -> ChainGaps:
        return self._get_chain_gaps(self.db)

    @classmethod
    def _get_chain_gaps(cls, db: DatabaseAPI) -> ChainGaps:
        try:
            encoded_gaps = db[SchemaV1.make_chain_gaps_lookup_key()]
        except KeyError:
            return GENESIS_CHAIN_GAPS
        else:
            return rlp.decode(encoded_gaps, sedes=chain_gaps)

    @classmethod
    def _update_chain_gaps(
        cls, db: DatabaseAPI, persisted_block: BlockAPI, base_gaps: ChainGaps = None
    ) -> GapInfo:
        # If we make many updates in a row, we can avoid reloading the integrity info by
        # continuously caching it and providing it as a parameter to this API
        if base_gaps is None:
            base_gaps = cls._get_chain_gaps(db)

        gap_change, gaps = fill_gap(persisted_block.number, base_gaps)
        if gap_change is not GapChange.NoChange:
            db.set(
                SchemaV1.make_chain_gaps_lookup_key(),
                rlp.encode(gaps, sedes=chain_gaps),
            )

        return gap_change, gaps

    @classmethod
    def _update_header_chain_gaps(
        cls,
        db: DatabaseAPI,
        persisting_header: BlockHeaderAPI,
        base_gaps: ChainGaps = None,
    ) -> GapInfo:
        # The only reason we overwrite this here is to be able to detect when the
        # HeaderDB de-canonicalizes an uncle that should cause us to
        # re-open a block gap.
        gap_change, gaps = super()._update_header_chain_gaps(
            db, persisting_header, base_gaps
        )

        if gap_change is not GapChange.NoChange or persisting_header.block_number == 0:
            return gap_change, gaps

        # We have written a header for which block number we've already had a header.
        # This might be a sign of a de-canonicalized uncle.
        current_gaps = cls._get_chain_gaps(db)
        if not is_block_number_in_gap(persisting_header.block_number, current_gaps):
            # ChainDB believes we have that block. If the header has changed, we need to
            # re-open a gap for the corresponding block.
            old_canonical_header = cls._get_canonical_block_header_by_number(
                db, persisting_header.block_number
            )
            if old_canonical_header != persisting_header:
                updated_gaps = reopen_gap(persisting_header.block_number, current_gaps)
                db.set(
                    SchemaV1.make_chain_gaps_lookup_key(),
                    rlp.encode(updated_gaps, sedes=chain_gaps),
                )

        return gap_change, gaps

    #
    # Header API
    #
    def get_block_uncles(self, uncles_hash: Hash32) -> Tuple[BlockHeaderAPI, ...]:
        validate_word(uncles_hash, title="Uncles Hash")
        if uncles_hash == EMPTY_UNCLE_HASH:
            return ()
        try:
            encoded_uncles = self.db[uncles_hash]
        except KeyError as exc:
            raise HeaderNotFound(f"No uncles found for hash {uncles_hash!r}") from exc
        else:
            return tuple(
                rlp.decode(encoded_uncles, sedes=rlp.sedes.CountableList(HeaderSedes))
            )

    @classmethod
    def _decanonicalize_old_headers(
        cls,
        db: DatabaseAPI,
        numbers_to_decanonicalize: Sequence[BlockNumber],
    ) -> Tuple[BlockHeaderAPI, ...]:
        old_canonical_headers = []

        # remove transaction lookups for blocks that are no longer canonical
        for block_number in numbers_to_decanonicalize:
            try:
                old_hash = cls._get_canonical_block_hash(db, block_number)
            except HeaderNotFound:
                # no old block, and no more possible
                break
            else:
                old_header = cls._get_block_header_by_hash(db, old_hash)
                old_canonical_headers.append(old_header)
                try:
                    transaction_hashes = cls._get_block_transaction_hashes(
                        db, old_header
                    )
                    for transaction_hash in transaction_hashes:
                        cls._remove_transaction_from_canonical_chain(
                            db, transaction_hash
                        )
                except MissingTrieNode:
                    # If the transactions were never stored for the (now) non-canonical
                    # chain, then you don't need to remove them from the canonical chain
                    # lookup.
                    pass

        return tuple(old_canonical_headers)

    #
    # Block API
    #
    def persist_block(
        self, block: BlockAPI, genesis_parent_hash: Hash32 = GENESIS_PARENT_HASH
    ) -> Tuple[Tuple[Hash32, ...], Tuple[Hash32, ...]]:
        with self.db.atomic_batch() as db:
            return self._persist_block(db, block, genesis_parent_hash)

    def persist_unexecuted_block(
        self,
        block: BlockAPI,
        receipts: Tuple[ReceiptAPI, ...],
        genesis_parent_hash: Hash32 = GENESIS_PARENT_HASH,
    ) -> Tuple[Tuple[Hash32, ...], Tuple[Hash32, ...]]:
        tx_root_hash, tx_kv_nodes = make_trie_root_and_nodes(block.transactions)

        if tx_root_hash != block.header.transaction_root:
            raise ValidationError(
                f"Block's transaction_root ({block.header.transaction_root!r}) "
                f"does not match expected value: {tx_root_hash!r}"
            )

        receipt_root_hash, receipt_kv_nodes = make_trie_root_and_nodes(receipts)

        if receipt_root_hash != block.header.receipt_root:
            raise ValidationError(
                f"Block's receipt_root ({block.header.receipt_root!r}) "
                f"does not match expected value: {receipt_root_hash!r}"
            )

        with self.db.atomic_batch() as db:
            self._persist_trie_data_dict(db, receipt_kv_nodes)
            self._persist_trie_data_dict(db, tx_kv_nodes)

            return self._persist_block(db, block, genesis_parent_hash)

    @classmethod
    def _persist_block(
        cls, db: DatabaseAPI, block: BlockAPI, genesis_parent_hash: Hash32
    ) -> Tuple[Tuple[Hash32, ...], Tuple[Hash32, ...]]:
        header_chain = (block.header,)
        new_canonical_headers, old_canonical_headers = cls._persist_header_chain(
            db, header_chain, genesis_parent_hash
        )

        for header in new_canonical_headers:
            if header.hash == block.hash:
                # Most of the time this is called to persist a block whose parent is the
                # current head, so we optimize for that and read the tx hashes from the
                # block itself. This is specially important during a fast sync.
                tx_hashes = tuple(tx.hash for tx in block.transactions)
            else:
                tx_hashes = cls._get_block_transaction_hashes(db, header)

            for index, transaction_hash in enumerate(tx_hashes):
                cls._add_transaction_to_canonical_chain(
                    db, transaction_hash, header, index
                )

            # post-shanghai, look for withdrawals
            if hasattr(block, "withdrawals") and block.withdrawals not in (None, ()):
                withdrawal_hashes = tuple(
                    withdrawal.hash for withdrawal in block.withdrawals
                )
                for index, withdrawal_hash in enumerate(withdrawal_hashes):
                    cls._add_withdrawal_to_canonical_chain(
                        db,
                        withdrawal_hash,
                        header,
                        index,
                    )

        if block.uncles:
            uncles_hash = cls._persist_uncles(db, block.uncles)
        else:
            uncles_hash = EMPTY_UNCLE_HASH
        if uncles_hash != block.header.uncles_hash:
            raise ValidationError(
                f"Block's uncles_hash ({block.header.uncles_hash}) does not match "
                f"actual uncles' hash ({uncles_hash})"
            )
        new_canonical_hashes = tuple(header.hash for header in new_canonical_headers)
        old_canonical_hashes = tuple(header.hash for header in old_canonical_headers)

        cls._update_chain_gaps(db, block)
        return new_canonical_hashes, old_canonical_hashes

    def persist_uncles(self, uncles: Tuple[BlockHeaderAPI]) -> Hash32:
        return self._persist_uncles(self.db, uncles)

    @staticmethod
    def _persist_uncles(db: DatabaseAPI, uncles: Tuple[BlockHeaderAPI, ...]) -> Hash32:
        uncles_hash = keccak(rlp.encode(uncles))
        db.set(
            uncles_hash,
            rlp.encode(uncles, sedes=rlp.sedes.CountableList(HeaderSedes)),
        )
        return cast(Hash32, uncles_hash)

    #
    # Block Data API (Transactions, Receipts, and Withdrawals)
    #
    @staticmethod
    def _get_block_data_from_root_hash(
        db: DatabaseAPI,
        block_root_hash: Hash32,
    ) -> Iterable[Hash32]:
        """
        Returns iterable of the encoded items from a root hash in a block. This can be
        useful for retrieving encoded transactions or withdrawals from the
        transaction_root or withdrawals_root of a block.
        """
        item_db = HexaryTrie(db, root_hash=block_root_hash)
        for item_idx in itertools.count():
            item_key = rlp.encode(item_idx)
            encoded = item_db[item_key]
            if encoded != b"":
                yield encoded
            else:
                break

    #
    # Transaction API
    #
    def add_receipt(
        self, block_header: BlockHeaderAPI, index_key: int, receipt: ReceiptAPI
    ) -> Hash32:
        receipt_db = HexaryTrie(db=self.db, root_hash=block_header.receipt_root)
        receipt_db[index_key] = receipt.encode()
        return receipt_db.root_hash

    def add_transaction(
        self,
        block_header: BlockHeaderAPI,
        index_key: int,
        transaction: SignedTransactionAPI,
    ) -> Hash32:
        transaction_db = HexaryTrie(self.db, root_hash=block_header.transaction_root)
        transaction_db[index_key] = transaction.encode()
        return transaction_db.root_hash

    def get_block_transactions(
        self, header: BlockHeaderAPI, transaction_decoder: Type[TransactionDecoderAPI]
    ) -> Tuple[SignedTransactionAPI, ...]:
        return self._get_block_transactions(
            header.transaction_root, transaction_decoder
        )

    def get_block_transaction_hashes(
        self, block_header: BlockHeaderAPI
    ) -> Tuple[Hash32, ...]:
        """
        Returns an iterable of the transaction hashes from the block specified
        by the given block header.
        """
        return self._get_block_transaction_hashes(self.db, block_header)

    @classmethod
    @to_tuple
    def _get_block_transaction_hashes(
        cls, db: DatabaseAPI, block_header: BlockHeaderAPI
    ) -> Iterable[Hash32]:
        all_encoded_transactions = cls._get_block_data_from_root_hash(
            db,
            block_header.transaction_root,
        )
        for encoded_transaction in all_encoded_transactions:
            yield cast(Hash32, keccak(encoded_transaction))

    @to_tuple
    def get_receipts(
        self, header: BlockHeaderAPI, receipt_decoder: Type[ReceiptDecoderAPI]
    ) -> Iterable[ReceiptAPI]:
        receipt_db = HexaryTrie(db=self.db, root_hash=header.receipt_root)
        for receipt_idx in itertools.count():
            receipt_key = rlp.encode(receipt_idx)
            receipt_data = receipt_db[receipt_key]
            if receipt_data != b"":
                yield receipt_decoder.decode(receipt_data)
            else:
                break

    def get_transaction_by_index(
        self,
        block_number: BlockNumber,
        transaction_index: int,
        transaction_decoder: Type[TransactionDecoderAPI],
    ) -> SignedTransactionAPI:
        try:
            block_header = self.get_canonical_block_header_by_number(block_number)
        except HeaderNotFound:
            raise TransactionNotFound(
                f"Block {block_number} is not in the canonical chain"
            )
        transaction_db = HexaryTrie(self.db, root_hash=block_header.transaction_root)
        encoded_index = rlp.encode(transaction_index)
        encoded_transaction = transaction_db[encoded_index]
        if encoded_transaction != b"":
            return transaction_decoder.decode(encoded_transaction)
        else:
            raise TransactionNotFound(
                f"No transaction is at index {transaction_index} "
                f"of block {block_number}"
            )

    def get_transaction_index(
        self, transaction_hash: Hash32
    ) -> Tuple[BlockNumber, int]:
        key = SchemaV1.make_transaction_hash_to_block_lookup_key(transaction_hash)
        try:
            encoded_key = self.db[key]
        except KeyError:
            raise TransactionNotFound(
                f"Transaction {encode_hex(transaction_hash)} "
                "not found in canonical chain"
            )

        transaction_key = rlp.decode(encoded_key, sedes=BlockDataKey)
        return (transaction_key.block_number, transaction_key.index)

    def get_receipt_by_index(
        self,
        block_number: BlockNumber,
        receipt_index: int,
        receipt_decoder: Type[ReceiptDecoderAPI],
    ) -> ReceiptAPI:
        try:
            block_header = self.get_canonical_block_header_by_number(block_number)
        except HeaderNotFound:
            raise ReceiptNotFound(f"Block {block_number} is not in the canonical chain")

        receipt_db = HexaryTrie(db=self.db, root_hash=block_header.receipt_root)
        receipt_key = rlp.encode(receipt_index)
        receipt_data = receipt_db[receipt_key]
        if receipt_data != b"":
            return receipt_decoder.decode(receipt_data)
        else:
            raise ReceiptNotFound(
                f"Receipt with index {receipt_index} not found in block"
            )

    @functools.lru_cache(maxsize=32)  # noqa: B019
    @to_tuple
    def _get_block_transactions(
        self, transaction_root: Hash32, transaction_decoder: Type[TransactionDecoderAPI]
    ) -> Iterable[SignedTransactionAPI]:
        """
        Memoizable version of `get_block_transactions`
        """
        for encoded_transaction in self._get_block_data_from_root_hash(
            self.db, transaction_root
        ):
            yield transaction_decoder.decode(encoded_transaction)

    @staticmethod
    def _remove_transaction_from_canonical_chain(
        db: DatabaseAPI, transaction_hash: Hash32
    ) -> None:
        """
        Removes the transaction specified by the given hash from the canonical
        chain.
        """
        db.delete(SchemaV1.make_transaction_hash_to_block_lookup_key(transaction_hash))

    @staticmethod
    def _add_transaction_to_canonical_chain(
        db: DatabaseAPI,
        transaction_hash: Hash32,
        block_header: BlockHeaderAPI,
        index: int,
    ) -> None:
        """
        :param bytes transaction_hash: the hash of the transaction to add the lookup for
        :param block_header: The header of the block with the txn that is in the
            canonical chain
        :param int index: the position of the transaction in the block
        - add lookup from transaction hash to the block number and index that the body
            is stored at
        - remove transaction hash to body lookup in the pending pool
        """
        transaction_key = BlockDataKey(block_header.block_number, index)
        db.set(
            SchemaV1.make_transaction_hash_to_block_lookup_key(transaction_hash),
            rlp.encode(transaction_key),
        )

    #
    # Withdrawals API
    #
    def get_block_withdrawals(
        self,
        header: BlockHeaderAPI,
    ) -> Tuple[WithdrawalAPI, ...]:
        return self._get_block_withdrawals(header.withdrawals_root)

    @functools.lru_cache(maxsize=32)  # noqa: B019
    @to_tuple
    def _get_block_withdrawals(
        self,
        withdrawals_root: Hash32,
    ) -> Iterable[WithdrawalAPI]:
        """
        Memoizable version of `get_block_withdrawals`
        """
        for encoded_withdrawal in self._get_block_data_from_root_hash(
            self.db,
            withdrawals_root,
        ):
            yield rlp.decode(encoded_withdrawal, sedes=Withdrawal)

    @staticmethod
    def _add_withdrawal_to_canonical_chain(
        db: DatabaseAPI,
        withdrawal_hash: Hash32,
        block_header: BlockHeaderAPI,
        index: int,
    ) -> None:
        withdrawal_key = BlockDataKey(block_header.block_number, index)
        db.set(
            SchemaV1.make_withdrawal_hash_to_block_lookup_key(withdrawal_hash),
            rlp.encode(withdrawal_key),
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
            self._persist_trie_data_dict(db, trie_data_dict)

    @classmethod
    def _persist_trie_data_dict(
        cls, db: DatabaseAPI, trie_data_dict: Dict[Hash32, bytes]
    ) -> None:
        for key, value in trie_data_dict.items():
            db[key] = value
