import itertools

import rlp

from trie import (
    Trie,
)

from eth_utils import (
    to_list,
)

from evm.constants import (
    BLANK_ROOT_HASH,
    GENESIS_DIFFICULTY,
    GENESIS_PARENT_HASH,
)
from evm.exceptions import (
    BlockNotFound,
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


class BaseChainDB:

    def __init__(self, db):
        self.db = JournalDB(db)

    def exists(self, key):
        return self.db.exists(key)

    def get_score(self, block_hash):
        # TODO: This may be a problem as not all chains will start with the same
        # genesis difficulty. Maybe make it Chain aware so that it can pull the
        # genesis block and pull the genesis difficulty from there.
        if block_hash == GENESIS_PARENT_HASH:
            return GENESIS_DIFFICULTY
        return rlp.decode(
            self.db.get(make_block_hash_to_score_lookup_key(block_hash)),
            sedes=rlp.sedes.big_endian_int)

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

    def add_block_number_to_hash_lookup(self, block):
        block_number_to_hash_key = make_block_number_to_hash_lookup_key(
            block.header.block_number
        )
        self.db.set(
            block_number_to_hash_key,
            rlp.encode(block.hash, sedes=rlp.sedes.binary),
        )

    def persist_block_to_db(self, block):
        # Persist the block header
        self.db.set(
            block.header.hash,
            rlp.encode(block.header),
        )

        score = self.get_score(block.header.parent_hash) + block.header.difficulty
        self.db.set(
            make_block_hash_to_score_lookup_key(block.hash),
            rlp.encode(score, sedes=rlp.sedes.big_endian_int))

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
