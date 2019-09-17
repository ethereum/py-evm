from typing import (
    Sequence,
    Tuple,
    Type,
)

import rlp
from rlp.sedes import (
    CountableList,
)

from eth_bloom import (
    BloomFilter,
)

from eth_typing import (
    BlockNumber,
    Hash32,
)

from eth_hash.auto import keccak

from eth.abc import (
    BlockHeaderAPI,
    ChainDatabaseAPI,
    ReceiptAPI,
    SignedTransactionAPI,
)
from eth.constants import (
    EMPTY_UNCLE_HASH,
)
from eth.rlp.blocks import (
    BaseBlock,
)
from eth.rlp.headers import (
    BlockHeader,
)
from eth.rlp.receipts import (
    Receipt,
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

    def __init__(self,
                 header: BlockHeaderAPI,
                 transactions: Sequence[SignedTransactionAPI]=None,
                 uncles: Sequence[BlockHeaderAPI]=None) -> None:
        if transactions is None:
            transactions = []
        if uncles is None:
            uncles = []

        self.bloom_filter = BloomFilter(header.bloom)

        super().__init__(
            header=header,
            transactions=transactions,
            uncles=uncles,
        )
        # TODO: should perform block validation at this point?

    #
    # Helpers
    #
    @property
    def number(self) -> BlockNumber:
        return self.header.block_number

    @property
    def hash(self) -> Hash32:
        return self.header.hash

    #
    # Transaction class for this block class
    #
    @classmethod
    def get_transaction_class(cls) -> Type[SignedTransactionAPI]:
        return cls.transaction_class

    #
    # Receipts API
    #
    def get_receipts(self, chaindb: ChainDatabaseAPI) -> Tuple[ReceiptAPI, ...]:
        return chaindb.get_receipts(self.header, Receipt)

    #
    # Header API
    #
    @classmethod
    def from_header(cls, header: BlockHeaderAPI, chaindb: ChainDatabaseAPI) -> "FrontierBlock":
        """
        Returns the block denoted by the given block header.
        """
        if header.uncles_hash == EMPTY_UNCLE_HASH:
            uncles: Tuple[BlockHeader, ...] = ()
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
    def add_uncle(self, uncle: BlockHeaderAPI) -> "FrontierBlock":
        self.uncles.append(uncle)
        self.header.uncles_hash = keccak(rlp.encode(self.uncles))
        return self
