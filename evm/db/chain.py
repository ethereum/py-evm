import itertools

import rlp

from trie import (
    HexaryTrie,
)

from eth_utils import (
    keccak,
    to_list,
    to_tuple,
)

from evm.constants import (
    BLANK_ROOT_HASH,
    GENESIS_PARENT_HASH,
)
from evm.exceptions import (
    BlockNotFound,
    CanonicalHeadNotFound,
    ParentNotFound,
    TransactionNotFound,
)
from evm.db.journal import (
    JournalDB,
)
from evm.db.state import (
    AccountStateDB,
)
from evm.rlp.headers import (
    BlockHeader,
)
from evm.utils.hexadecimal import (
    encode_hex,
)
from evm.validation import (
    validate_uint256,
    validate_word,
)
from evm.utils.db import (
    make_block_hash_to_score_lookup_key,
    make_block_number_to_hash_lookup_key,
    make_transaction_hash_to_block_lookup_key,
    make_transaction_hash_to_data_lookup_key,
)


CANONICAL_HEAD_HASH_DB_KEY = b'v1:canonical_head_hash'


class TransactionKey(rlp.Serializable):
    fields = [
        ('block_number', rlp.sedes.big_endian_int),
        ('index', rlp.sedes.big_endian_int),
    ]


class BaseChainDB:

    def __init__(self, db):
        self.db = JournalDB(db)

    def exists(self, key):
        return self.db.exists(key)

    def get_canonical_head(self):
        if not self.exists(CANONICAL_HEAD_HASH_DB_KEY):
            raise CanonicalHeadNotFound("No canonical head set for this chain")
        return self.get_block_header_by_hash(self.db.get(CANONICAL_HEAD_HASH_DB_KEY))

    def get_canonical_block_header_by_number(self, block_number):
        """
        Returns the block header with the given number in the canonical chain.

        Raises BlockNotFound if there's no block header with the given number in the
        canonical chain.
        """
        validate_uint256(block_number, title="Block Number")
        return self.get_block_header_by_hash(self.lookup_block_hash(block_number))

    def get_score(self, block_hash):
        return rlp.decode(
            self.db.get(make_block_hash_to_score_lookup_key(block_hash)),
            sedes=rlp.sedes.big_endian_int)

    def _set_as_canonical_chain_head(self, header):
        """
        :returns: iterable of headers newly on the canonical head
        """
        new_canonical_headers = tuple(reversed(self.find_common_ancestor(header)))

        # TODO move hash-> block id lookup to pending, to indicate that transaction is not in canonical chain
        for h in new_canonical_headers:
            try:
                old_hash = self.lookup_block_hash(h.block_number)
            except KeyError:
                # no old block, keep looking
                continue
            else:
                old_header = self.get_block_header_by_hash(header.hash)
                for transaction_hash in self.get_block_transaction_hashes(old_header):
                    # TODO remove from txn block lookup
                    # TODO re-add txn to sent pool (only if local sender)
                    pass

        for h in new_canonical_headers:
            self.add_block_number_to_hash_lookup(h)

        try:
            self.get_block_header_by_hash(header.hash)
        except BlockNotFound:
            raise ValueError("Cannot use unknown block hash as canonical head: {}".format(
                header.hash))
        self.db.set(CANONICAL_HEAD_HASH_DB_KEY, header.hash)

        return new_canonical_headers

    @to_tuple
    def find_common_ancestor(self, header):
        """
        Returns the chain leading up from the given header until the first ancestor it has in
        common with our canonical chain.
        """
        h = header
        while True:
            yield h
            if h.parent_hash == GENESIS_PARENT_HASH:
                break
            try:
                orig = self.get_canonical_block_header_by_number(h.block_number)
            except KeyError:
                # This just means the block is not on the canonical chain.
                pass
            else:
                if orig.hash == h.hash:
                    # Found the common ancestor, stop.
                    break
            h = self.get_block_header_by_hash(h.parent_hash)

    def get_block_header_by_hash(self, block_hash):
        """
        Returns the requested block header as specified by block hash.

        Raises BlockNotFound if it is not present in the db.
        """
        validate_word(block_hash, title="Block Hash")
        try:
            block = self.db.get(block_hash)
        except KeyError:
            raise BlockNotFound("No block with hash {0} found".format(
                encode_hex(block_hash)))
        return rlp.decode(block, sedes=BlockHeader)

    def header_exists(self, block_hash):
        """Returns True if the header with the given block hash is in our DB."""
        return self.db.exists(block_hash)

    def lookup_block_hash(self, block_number):
        """
        Return the block hash for the given block number.
        """
        validate_uint256(block_number, title="Block Number")
        number_to_hash_key = make_block_number_to_hash_lookup_key(block_number)
        return rlp.decode(
            self.db.get(number_to_hash_key),
            sedes=rlp.sedes.binary,
        )

    def get_block_uncles(self, uncles_hash):
        validate_word(uncles_hash, title="Uncles Hash")
        return rlp.decode(self.db.get(uncles_hash), sedes=rlp.sedes.CountableList(BlockHeader))

    @to_list
    def get_receipts(self, header, receipt_class):
        receipt_db = HexaryTrie(db=self.db, root_hash=header.receipt_root)
        for receipt_idx in itertools.count():
            receipt_key = rlp.encode(receipt_idx)
            if receipt_key in receipt_db:
                receipt_data = receipt_db[receipt_key]
                yield rlp.decode(receipt_data, sedes=receipt_class)
            else:
                break

    def _get_block_transaction_data(self, block_header):
        '''
        :returns: iterable of encoded transactions for the given block header
        '''
        transaction_db = HexaryTrie(self.db, root_hash=block_header.transaction_root)
        for transaction_idx in itertools.count():
            transaction_key = rlp.encode(transaction_idx)
            if transaction_key in transaction_db:
                yield transaction_db[transaction_key]
            else:
                break

    @to_list
    def get_block_transaction_hashes(self, block_header):
        for encoded_transaction in self._get_block_transaction_data(block_header):
            yield keccak(encoded_transaction)

    @to_list
    def get_block_transactions(self, block_header, transaction_class):
        for encoded_transaction in self._get_block_transaction_data(block_header):
            yield rlp.decode(encoded_transaction, sedes=transaction_class)

    def get_transaction_by_key(self, block_number, transaction_index, transaction_class):
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
            return None

    def get_pending_transaction(self, transaction_hash, transaction_class):
        try:
            data = self.db.get(make_transaction_hash_to_data_lookup_key(transaction_hash))
            return rlp.decode(data, sedes=transaction_class)
        except KeyError:
            raise TransactionNotFound(
                "Transaction with hash {} not found".format(encode_hex(transaction_hash)))

    def get_transaction_key(self, transaction_hash, transaction_class):
        try:
            encoded_key = self.db.get(make_transaction_hash_to_block_lookup_key(transaction_hash))
        except KeyError:
            raise TransactionNotFound(
                "Transaction {} not found in canonical chain".format(encode_hex(transaction_hash)))

        transaction_key = rlp.decode(encoded_key, sedes=TransactionKey)
        return (transaction_key.block_number, transaction_key.index)

    def add_block_number_to_hash_lookup(self, header):
        block_number_to_hash_key = make_block_number_to_hash_lookup_key(
            header.block_number
        )
        self.db.set(
            block_number_to_hash_key,
            rlp.encode(header.hash, sedes=rlp.sedes.binary),
        )

    # TODO: This method sould take a chain of headers as that's the most common use case
    # and it'd be much faster than inserting each header individually.
    def persist_header_to_db(self, header):
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
                new_headers = []

        return new_headers

    def persist_block_to_db(self, block):
        '''
        Chain must do follow-up work to persist transactions to db
        '''
        new_canonical_headers = self.persist_header_to_db(block.header)

        # Persist the transaction bodies
        transaction_db = HexaryTrie(self.db, root_hash=BLANK_ROOT_HASH)
        for i, transaction in enumerate(block.transactions):
            index_key = rlp.encode(i, sedes=rlp.sedes.big_endian_int)
            transaction_db[index_key] = rlp.encode(transaction)
        assert transaction_db.root_hash == block.header.transaction_root

        for header in new_canonical_headers:
            for transaction_hash in self.get_block_transaction_hashes(header):
                self._add_transaction_to_canonical_chain(transaction_hash, header.hash)

        # Persist the uncles list
        self.db.set(
            block.header.uncles_hash,
            rlp.encode(block.uncles, sedes=rlp.sedes.CountableList(type(block.header))),
        )

    def _add_transaction_to_canonical_chain(self, transaction, block_header, transaction_index):
        '''
        - add lookup from transaction hash to the block number and index that the body is stored at
        - remove transaction hash to body lookup in the pending pool
        '''
        transaction_key = TransactionKey(block_header.block_number, transaction_index)
        self.db.set(
            make_transaction_hash_to_block_lookup_key(transaction.hash),
            rlp.encode(transaction_key),
        )

        # because transaction is now in canonical chain, can now remove from pending txn lookups
        self.db.delete(make_transaction_hash_to_data_lookup_key(transaction.hash))

    def _add_transaction_hash_to_data_lookup(self, transaction):
        self.db.set(
            make_transaction_hash_to_data_lookup_key(transaction.hash),
            rlp.encode(transaction),
        )

    def add_transaction(self, block_header, index_key, transaction):
        transaction_db = HexaryTrie(self.db, root_hash=block_header.transaction_root)
        transaction_db[index_key] = rlp.encode(transaction)
        self._add_transaction_hash_to_data_lookup(transaction)
        return transaction_db.root_hash

    def add_receipt(self, block_header, index_key, receipt):
        receipt_db = HexaryTrie(db=self.db, root_hash=block_header.receipt_root)
        receipt_db[index_key] = rlp.encode(receipt)
        return receipt_db.root_hash

    def snapshot(self):
        return self.db.snapshot()

    def revert(self, checkpoint):
        self.db.revert(checkpoint)

    def commit(self, checkpoint):
        self.db.commit(checkpoint)

    def clear(self):
        self.db.clear()

    def get_state_db(self, state_root, read_only):
        return AccountStateDB(db=self.db, root_hash=state_root, read_only=read_only)
