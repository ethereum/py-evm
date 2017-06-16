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

from evm.utils.transactions import (
    get_transactions_from_db,
)
from evm.utils.receipts import (
    get_receipts_from_db,
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

    db = None
    bloom_filter = None

    def __init__(self, header, transactions=[], uncles=[], db=None):
        if db is not None:
            self.db = db

        if self.db is None:
            raise TypeError("Block must have a db")

        self.bloom_filter = BloomFilter(header.bloom)
        self.transaction_db = Trie(db=self.db, root_hash=header.transaction_root)
        self.receipt_db = Trie(db=self.db, root_hash=header.receipt_root)

        super(FrontierBlock, self).__init__(
            header=header,
            transactions=transactions,
            uncles=uncles,
        )
        # TODO: should perform block validation at this point?

    #
    # Helpers
    #
    @property
    def number(self):
        return self.header.block_number

    #
    # Transaction class for this block class
    #
    transaction_class = FrontierTransaction

    @classmethod
    def get_transaction_class(cls):
        return cls.transaction_class

    #
    # Gas Usage API
    #
    def get_cumulative_gas_used(self):
        """
        Note return value of this function can be cached based on
        `self.receipt_db.root_hash`
        """
        if len(self.transactions):
            return self.receipts[-1].gas_used
        else:
            return 0

    #
    # Receipts API
    #
    @property
    def receipts(self):
        return get_receipts_from_db(self.receipt_db, Receipt)

    #
    # Header API
    #
    @classmethod
    def from_header(cls, header):
        """
        Returns the block denoted by the given block header.
        """
        uncles = rlp.decode(cls.db.get(header.uncles_hash), sedes=CountableList(BlockHeader))

        transaction_db = Trie(cls.db, root_hash=header.transaction_root)
        transactions = get_transactions_from_db(transaction_db, cls.get_transaction_class())

        return cls(
            header=header,
            transactions=transactions,
            uncles=uncles,
        )

    #
    # Execution API
    #
    def apply_transaction(self, evm, transaction):
        computation = evm.apply_transaction(transaction)

        logs = [
            Log(address, topics, data)
            for address, topics, data
            in computation.get_log_entries()
        ]
        receipt = Receipt(
            state_root=computation.state_db.root_hash,
            gas_used=transaction.get_intrensic_gas() + computation.get_gas_used(),
            logs=logs,
        )

        transaction_idx = len(self.transactions)

        index_key = rlp.encode(transaction_idx, sedes=rlp.sedes.big_endian_int)

        self.transactions.append(transaction)

        self.transaction_db[index_key] = rlp.encode(transaction)
        self.receipt_db[index_key] = rlp.encode(receipt)

        self.bloom_filter |= receipt.bloom

        self.header.transaction_root = self.transaction_db.root_hash
        self.header.state_root = computation.state_db.root_hash
        self.header.receipt_root = self.receipt_db.root_hash
        self.header.bloom = int(self.bloom_filter)
        self.header.gas_used = self.get_cumulative_gas_used()

        return computation

    def mine(self, **kwargs):
        """
        - `uncles_hash`
        - `state_root`
        - `transaction_root`
        - `receipt_root`
        - `bloom`
        - `gas_used`
        - `extra_data`
        - `mix_hash`
        - `nonce`
        """
        header = self.header
        provided_fields = set(kwargs.keys())
        known_fields = set(tuple(zip(*BlockHeader.fields))[0])
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

        # TODO: do we validate here!?
        return self
