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
from evm.rlp.logs import (
    Log,
)
from evm.rlp.receipts import (
    Receipt,
)
from evm.rlp.blocks import (
    BaseBlock,
)
from evm.rlp.headers import (
    BlockHeader,
)

from .transactions import (
    FrontierTransaction,
)


class FrontierBlock(BaseBlock):
    fields = [
        ('header', BlockHeader),
        ('transactions', CountableList(FrontierTransaction)),
        ('uncles', CountableList(BlockHeader))
    ]

    def __init__(self, header, db=None):
        if db is not None:
            self.db = db

        if self.db is None:
            raise TypeError("Block must have a db")

        # NOTE: setting the header also sets the `self.bloom_filter` property
        self.header = header

        # TODO: tons more validation......
        # - transaction_root vs self.transactions
        # - receipts_root vs self.receipts

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

    #
    # Receipt API
    #
    bloom_filter = None

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

    #
    # Gas Usage API
    #
    @property
    def cumulative_gas_used(self):
        """
        Note return value of this function can be cached based on
        `self.receipt_db.root_hash`
        """
        return sum(receipt.gas_used for receipt in self.receipts)

    #
    # Header API
    #
    _static_header_params = None

    @property
    def header(self):
        """
        The block header is a computed property for open blocks each time.
        """
        return BlockHeader(**self._get_header_params())

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

        self._static_header_params = {
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

        self.bloom_filter = BloomFilter(value.bloom)
        self.state_db = State(self.db, root_hash=value.state_root)
        self.transaction_db = Trie(self.db, root_hash=value.transaction_root)
        self.receipt_db = Trie(self.db, root_hash=value.receipts_root)

    def _get_header_params(self):
        return {
            # static values
            'parent_hash': self._static_header_params['parent_hash'],
            'coinbase': self._static_header_params['coinbase'],
            'difficulty': self._static_header_params['difficulty'],
            'block_number': self._static_header_params['block_number'],
            'gas_limit': self._static_header_params['gas_limit'],
            'timestamp': self._static_header_params['timestamp'],
            'extra_data': self._static_header_params['extra_data'],
            'mix_hash': self._static_header_params['mix_hash'],
            'nonce': self._static_header_params['nonce'],
            # dynamic values
            'uncles_hash': EMPTY_UNCLE_HASH,
            'state_root': self.state_db.state_root,
            'transaction_root': self.transaction_db.root_hash,
            'receipts_root': self.receipt_db.root_hash,
            'bloom': int(self.bloom_filter),
            'gas_used': self.cumulative_gas_used,
        }

    def apply_transaction(self, evm, transaction):
        computation = evm.apply_transaction(transaction)

        logs = [
            Log(address, topics, data)
            for address, topics, data
            in computation.get_log_entries()
        ]
        receipt = Receipt(
            state_root=self.state_db.state_root,
            gas_used=computation.get_gas_used(),
            logs=logs,
        )

        transaction_idx = len(self.transactions)
        transaction_key = rlp.encode(transaction_idx)

        self.transaction_db[transaction_key] = rlp.encode(transaction)
        self.receipt_db[transaction_key] = rlp.encode(receipt)
        self.bloom_filter |= receipt.bloom
        return computation

    def mine(self, **kwargs):
        """
        - `uncles_hash`
        - `state_root`
        - `transaction_root`
        - `receipts_root`
        - `bloom`
        - `gas_used`
        - `extra_data`
        - `mix_hash`
        - `nonce`
        """
        header = self.header
        provided_fields = set(kwargs.keys())
        known_fields = set(tuple(zip(BlockHeader.fields))[0])
        unknown_fields = provided_fields.difference(known_fields)

        if unknown_fields:
            raise AttributeError(
                "Unable to set the field(s) {0} on the `BlockHeader` class. "
                "Received the following unexpected fields: {0}.".format(
                    ", ".join(unknown_fields),
                    ", ".join(known_fields),
                )
            )

        for key, value in kwargs.items():
            setattr(header, key, value)

        mined_block = self.block.mine(**kwargs)
        # TODO: validation....!!!!

        self.header = BlockHeader.from_parent(mined_block.header)
        # TODO: validation....!!!!

        return self
