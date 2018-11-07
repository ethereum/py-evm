from typing import (  # noqa: F401
    Iterable,
    List,
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
    Hash32,
)

from eth_hash.auto import keccak

from eth.constants import (
    EMPTY_UNCLE_HASH,
)

from eth.db.chain import (
    BaseChainDB,
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
from eth.rlp.transactions import (
    BaseTransaction,
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
                 header: BlockHeader,
                 transactions: Iterable[BaseTransaction]=None,
                 uncles: Iterable[BlockHeader]=None) -> None:
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
    def number(self) -> int:
        return self.header.block_number

    @property
    def hash(self) -> Hash32:
        return self.header.hash

    #
    # Transaction class for this block class
    #
    @classmethod
    def get_transaction_class(cls) -> Type[BaseTransaction]:
        return cls.transaction_class

    #
    # Receipts API
    #
    def get_receipts(self, chaindb: BaseChainDB) -> Iterable[Receipt]:
        return chaindb.get_receipts(self.header, Receipt)

    #
    # Header API
    #
    @classmethod
    def from_header(cls, header: BlockHeader, chaindb: BaseChainDB) -> BaseBlock:
        """
        Returns the block denoted by the given block header.
        """
        if header.uncles_hash == EMPTY_UNCLE_HASH:
            uncles = []  # type: List[BlockHeader]
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
    def add_uncle(self, uncle: BlockHeader) -> "FrontierBlock":
        self.uncles.append(uncle)
        self.header.uncles_hash = keccak(rlp.encode(self.uncles))
        return self
