from typing import (
    List,
    Sequence,
    Type,
)

from eth_utils import (
    humanize_hash,
)
import rlp

from eth._utils.datatypes import (
    Configurable,
)
from eth.abc import (
    BlockAPI,
    BlockHeaderAPI,
    SignedTransactionAPI,
    TransactionBuilderAPI,
    WithdrawalAPI,
)


class BaseBlock(Configurable, rlp.Serializable, BlockAPI):
    transaction_builder: Type[TransactionBuilderAPI] = None

    def __init__(
        self,
        header: BlockHeaderAPI,
        transactions: Sequence[SignedTransactionAPI] = None,
        uncles: Sequence[BlockHeaderAPI] = None,
        withdrawals: Sequence[WithdrawalAPI] = None,
    ) -> None:
        if withdrawals is not None:
            rlp.Serializable.__init__(
                self,
                header=header,
                transactions=transactions,
                uncles=uncles,
                withdrawals=withdrawals,
            )
        else:
            rlp.Serializable.__init__(
                self,
                header=header,
                transactions=transactions,
                uncles=uncles,
            )
        self.block_requests: List[bytes] = []

    @classmethod
    def get_transaction_builder(cls) -> Type[TransactionBuilderAPI]:
        if cls.transaction_builder is None:
            raise AttributeError("Block subclasses must declare a transaction_builder")
        return cls.transaction_builder

    @property
    def is_genesis(self) -> bool:
        return self.header.is_genesis

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(#{str(self)})>"

    def __str__(self) -> str:
        clipped_hash = humanize_hash(self.hash)
        return f"Block #{self.number}-0x{clipped_hash}"
