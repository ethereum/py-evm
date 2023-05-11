from typing import (
    Sequence,
    Tuple,
    Type,
)

from eth_bloom import (
    BloomFilter,
)
from eth_typing import (
    BlockNumber,
    Hash32,
)
from rlp.sedes import (
    CountableList,
)
from trie.exceptions import (
    MissingTrieNode,
)

from eth.abc import (
    BlockHeaderAPI,
    ChainDatabaseAPI,
    ReceiptAPI,
    ReceiptBuilderAPI,
    SignedTransactionAPI,
    TransactionBuilderAPI,
)
from eth.constants import (
    EMPTY_UNCLE_HASH,
)
from eth.exceptions import (
    BlockNotFound,
    HeaderNotFound,
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
    transaction_builder = FrontierTransaction
    receipt_builder = Receipt
    fields = [
        ("header", BlockHeader),
        ("transactions", CountableList(transaction_builder)),
        ("uncles", CountableList(BlockHeader)),
    ]

    bloom_filter = None

    def __init__(
        self,
        header: BlockHeaderAPI,
        transactions: Sequence[SignedTransactionAPI] = None,
        uncles: Sequence[BlockHeaderAPI] = None,
    ) -> None:
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
    def get_transaction_builder(cls) -> Type[TransactionBuilderAPI]:
        return cls.transaction_builder

    @classmethod
    def get_receipt_builder(cls) -> Type[ReceiptBuilderAPI]:
        return cls.receipt_builder

    #
    # Receipts API
    #
    def get_receipts(self, chaindb: ChainDatabaseAPI) -> Tuple[ReceiptAPI, ...]:
        return chaindb.get_receipts(self.header, self.get_receipt_builder())

    #
    # Header API
    #
    @classmethod
    def from_header(
        cls, header: BlockHeaderAPI, chaindb: ChainDatabaseAPI
    ) -> "FrontierBlock":
        """
        Returns the block denoted by the given block header.

        :raise eth.exceptions.BlockNotFound: if transactions or uncle headers missing
        """
        if header.uncles_hash == EMPTY_UNCLE_HASH:
            uncles: Tuple[BlockHeaderAPI, ...] = ()
        else:
            try:
                uncles = chaindb.get_block_uncles(header.uncles_hash)
            except HeaderNotFound as exc:
                raise BlockNotFound(
                    f"Uncles not found in database for {header}: {exc}"
                ) from exc

        try:
            transactions = chaindb.get_block_transactions(
                header, cls.get_transaction_builder()
            )
        except MissingTrieNode as exc:
            raise BlockNotFound(
                f"Transactions not found in database for {header}: {exc}"
            ) from exc

        return cls(
            header=header,
            transactions=transactions,
            uncles=uncles,
        )
