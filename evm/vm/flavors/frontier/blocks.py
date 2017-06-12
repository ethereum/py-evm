import itertools

import rlp
from rlp.sedes import (
    CountableList,
)

from eth_bloom import (
    BloomFilter,
)

from trie import (
    Trie,
)

from evm.constants import (
    EMPTY_UNCLE_HASH,
)
from evm.state import (
    State,
)
from evm.rlp.receipts import (
    Receipt,
)
from evm.rlp.blocks import (
    BaseOpenBlock,
    BaseSealedBlock,
)
from evm.rlp.headers import (
    BlockHeader,
)

from .transactions import (
    FrontierTransaction,
)


class BaseFrontierBlock(object):
    fields = [
        ('header', BlockHeader),
        ('transactions', CountableList(FrontierTransaction)),
        ('uncles', CountableList(BlockHeader))
    ]


class SealedFrontierBlock(BaseFrontierBlock, BaseSealedBlock):
    pass


class OpenFrontierBlock(BaseFrontierBlock, BaseOpenBlock):
    bloom = None

    def __init__(self, header, db=None):
        self.db = db

        if self.db is None:
            raise TypeError("Block must have a db")

        self.header = header

        # TODO: tons more validation......
        # - transaction_root vs self.transactions
        # - receipts_root vs self.receipts

    _static_header_data = None

    #
    # Computed properties and methods
    #
    transaction_class = FrontierTransaction

    @classmethod
    def get_transaction_class(cls):
        return cls.transaction_class

    @property
    def transactions(self):
        return list(self._get_transactions())

    def _get_transactions(self):
        """
        Note: return value of this function can be cached based on the
        `self.transaction_db.root_hash` value.
        """
        for transaction_idx in itertools.count():
            transaction_key = rlp.encode(transaction_idx)
            if transaction_key in self.transaction_db:
                transaction_data = self.transaction_db[transaction_key]
                yield rlp.decode(transaction_data, sedes=self.get_transaction_class())
            else:
                break

    @property
    def receipts(self):
        return list(self._get_receipts())

    def _get_receipts(self):
        """
        Note: return value of this function can be cached based on the
        `self.receipt_db.root_hash` value.
        """
        for transaction_idx in itertools.count():
            transaction_key = rlp.encode(transaction_idx)
            if transaction_key in self.receipt_db:
                receipt_data = self.receipt_db[transaction_key]
                yield rlp.decode(receipt_data, sedes=Receipt)
            else:
                break

    @property
    def cumulative_gas_used(self):
        """
        Note return value of this function can be cached based on
        `self.receipt_db.root_hash`
        """
        return sum(receipt.gas_used for receipt in self.receipts)

    @property
    def header(self):
        """
        The block header is a computed property for open blocks each time.
        """
        return BlockHeader(**self.get_header_data())

    @header.setter
    def header(self, value):
        """
        Update this block to the values represented by the given header.
        """
        if not isinstance(value, BlockHeader):
            raise TypeError("block.header may only be set with a BlockHeader instance")

        if value.uncles_hash != EMPTY_UNCLE_HASH:
            # TODO: what to do about this?
            raise ValueError("Open blocks may not have uncles")

        self._static_header_data = {
            'parent_hash': value.parent_hash,
            'uncles_hash': value.uncles_hash,
            'coinbase': value.coinbase,
            'difficulty': value.difficulty,
            'block_number': value.block_number,
            'gas_limit': value.gas_limit,
            'timestamp': value.timestamp,
            'extra_data': value.extra_data,
            'mix_hash': value.mix_hash,
            'nonce': value.nonce,
        }

        self.bloom = BloomFilter(value.bloom)
        self.state_db = State(self.db, root_hash=value.state_root)
        self.transaction_db = Trie(self.db, root_hash=value.transaction_root)
        self.receipt_db = Trie(self.db, root_hash=value.receipts_root)

    def get_header_data(self):
        return {
            # static values
            'parent_hash': self._static_header_data['parent_hash'],
            'coinbase': self._static_header_data['coinbase'],
            'difficulty': self._static_header_data['difficulty'],
            'block_number': self._static_header_data['block_number'],
            'gas_limit': self._static_header_data['gas_limit'],
            'timestamp': self._static_header_data['timestamp'],
            'extra_data': self._static_header_data['extra_data'],
            'mix_hash': self._static_header_data['mix_hash'],
            'nonce': self._static_header_data['nonce'],
            # dynamic values
            'uncles_hash': EMPTY_UNCLE_HASH,
            'state_root': self.state_db.state.root_hash,
            'transaction_root': self.transaction_db.root_hash,
            'receipts_root': self.receipt_db.root_hash,
            'bloom': int(self.bloom),
            'gas_used': self.cumulative_gas_used,
        }

    def apply_transaction(self, evm, transaction):
        computation = evm.apply_transaction(transaction)

        receipt = Receipt(
            state_root=self.state_db.state_root,
            gas_used=self.total_gas_used(),
            logs=self.logs,
            bloom=self.bloom,  # TODO: logs?
        )

        transaction_idx = len(self.transactions)
        transaction_key = rlp.encode(transaction_idx)

        self.transaction_db[transaction_key] = rlp.encode(transaction)
        self.receipt_db[transaction_key] = rlp.encode(transaction)
        self.bloom |= receipt.bloom
        return computation

    sealed_block_class = SealedFrontierBlock

    def seal(self, uncles):
        return self.get_sealed_block_class()(
            header=self.header,
            transactions=self.transactions,
            uncles=uncles,
        )
