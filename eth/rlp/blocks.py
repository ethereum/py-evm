from typing import (
    Type
)

from eth_utils import (
    humanize_hash,
)

from eth._utils.datatypes import (
    Configurable,
)
from eth.abc import (
    BlockAPI,
    SignedTransactionAPI,
)


class BaseBlock(Configurable, BlockAPI):
    transaction_class: Type[SignedTransactionAPI] = None

    @classmethod
    def get_transaction_class(cls) -> Type[SignedTransactionAPI]:
        if cls.transaction_class is None:
            raise AttributeError("Block subclasses must declare a transaction_class")
        return cls.transaction_class

    @property
    def is_genesis(self) -> bool:
        return self.header.is_genesis

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}(#{str(self)})>'

    def __str__(self) -> str:
        clipped_hash = humanize_hash(self.hash)
        return f"Block #{self.number}-0x{clipped_hash}"
