import rlp
from rlp.sedes import (
    CountableList,
)

from eth_bloom import (
    BloomFilter,
)

from eth_utils import (
    keccak,
)

from evm.constants import (
    EMPTY_UNCLE_HASH,
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
    transaction_class = FrontierTransaction
    fields = [
        ('header', BlockHeader),
        ('transactions', CountableList(transaction_class)),
        ('uncles', CountableList(BlockHeader))
    ]

    bloom_filter = None

    def __init__(self, header, transactions=None, uncles=None):
        if transactions is None:
            transactions = []
        if uncles is None:
            uncles = []

        self.bloom_filter = BloomFilter(header.bloom)

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

    @property
    def hash(self):
        return self.header.hash

    #
    # Transaction class for this block class
    #
    @classmethod
    def get_transaction_class(cls):
        return cls.transaction_class

    #
    # Receipts API
    #
    def get_receipts(self, chaindb):
        return chaindb.get_receipts(self.header, Receipt)

    #
    # Header API
    #
    @classmethod
    def from_header(cls, header, chaindb):
        """
        Returns the block denoted by the given block header.
        """
        if header.uncles_hash == EMPTY_UNCLE_HASH:
            uncles = []
        else:
            uncles = chaindb.get_block_uncles(header.uncles_hash)

        transactions = chaindb.get_block_transactions(header, cls.get_transaction_class())

        return cls(
            header=header,
            transactions=transactions,
            uncles=uncles,
        )

    #
    # Execution API
    #
    def add_uncle(self, uncle):
        self.uncles.append(uncle)
        self.header.uncles_hash = keccak(rlp.encode(self.uncles))
        return self
