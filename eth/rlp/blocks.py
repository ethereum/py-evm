from typing import (
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
    TransactionBuilderAPI,
)


class BaseBlock(Configurable, rlp.Serializable, BlockAPI):
    transaction_builder: Type[TransactionBuilderAPI] = None

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
