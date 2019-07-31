from typing import (
    Type
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
        return '<{class_name}(#{b})>'.format(
            class_name=self.__class__.__name__,
            b=str(self),
        )

    def __str__(self) -> str:
        return "Block #{b.number}".format(b=self)
