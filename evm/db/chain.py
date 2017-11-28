import itertools

import rlp

from trie import (
    Trie,
)

from eth_utils import (
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
)
from evm.db.journal import (
    JournalDB,
)
from evm.db.state import (
    State,
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
)


CANONICAL_HEAD_HASH_DB_KEY = b'v1:canonical_head_hash'


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

    def set_as_canonical_chain_head(self, header):
        """
        Sets the header as the canonical chain HEAD.
        """
        for h in reversed(self.find_common_ancestor(header)):
            self.add_block_number_to_hash_lookup(h)

        try:
            self.get_block_header_by_hash(header.hash)
        except BlockNotFound:
            raise ValueError("Cannot use unknown block hash as canonical head: {}".format(
                header.hash))
        self.db.set(CANONICAL_HEAD_HASH_DB_KEY, header.hash)

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
        # TODO: can raise KeyError
        block_hash = rlp.decode(
            self.db.get(number_to_hash_key),
            sedes=rlp.sedes.binary,
        )
        return block_hash

    def get_block_uncles(self, uncles_hash):
        validate_word(uncles_hash, title="Uncles Hash")
        return rlp.decode(self.db.get(uncles_hash), sedes=rlp.sedes.CountableList(BlockHeader))

    @to_list
    def get_receipts(self, header, receipt_class):
        receipt_db = Trie(db=self.db, root_hash=header.receipt_root)
        for receipt_idx in itertools.count():
            receipt_key = rlp.encode(receipt_idx)
            if receipt_key in receipt_db:
                receipt_data = receipt_db[receipt_key]
                yield rlp.decode(receipt_data, sedes=receipt_class)
            else:
                break

    @to_list
    def get_block_transactions(self, block_header, transaction_class):
        transaction_db = Trie(self.db, root_hash=block_header.transaction_root)
        for transaction_idx in itertools.count():
            transaction_key = rlp.encode(transaction_idx)
            if transaction_key in transaction_db:
                transaction_data = transaction_db[transaction_key]
                yield rlp.decode(transaction_data, sedes=transaction_class)
            else:
                break

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
            self.set_as_canonical_chain_head(header)
        else:
            if score > head_score:
                self.set_as_canonical_chain_head(header)

    def persist_block_to_db(self, block):
        self.persist_header_to_db(block.header)

        # Persist the transactions
        transaction_db = Trie(self.db, root_hash=BLANK_ROOT_HASH)
        for i in range(len(block.transactions)):
            index_key = rlp.encode(i, sedes=rlp.sedes.big_endian_int)
            transaction_db[index_key] = rlp.encode(block.transactions[i])
        assert transaction_db.root_hash == block.header.transaction_root

        # Persist the uncles list
        self.db.set(
            block.header.uncles_hash,
            rlp.encode(block.uncles, sedes=rlp.sedes.CountableList(type(block.header))),
        )

    def add_transaction(self, block_header, index_key, transaction):
        transaction_db = Trie(self.db, root_hash=block_header.transaction_root)
        transaction_db[index_key] = rlp.encode(transaction)
        return transaction_db.root_hash

    def add_receipt(self, block_header, index_key, receipt):
        receipt_db = Trie(db=self.db, root_hash=block_header.receipt_root)
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
        return State(db=self.db, root_hash=state_root, read_only=read_only)
