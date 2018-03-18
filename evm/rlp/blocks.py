from abc import (
    ABCMeta,
    abstractmethod
)

import rlp

from evm.utils.datatypes import (
    Configurable,
)

from evm.db.chain import BaseChainDB

from .transactions import BaseTransaction
from .headers import BlockHeader


class BaseBlock(rlp.Serializable, Configurable, metaclass=ABCMeta):

    # TODO: Remove this once https://github.com/ethereum/pyrlp/issues/45 is
    # fixed.
    @classmethod
    def get_sedes(cls):
        return rlp.sedes.List(sedes for _, sedes in cls.fields)

    transaction_class = None

    @classmethod
    def get_transaction_class(cls) -> BaseTransaction:
        if cls.transaction_class is None:
            raise AttributeError("Block subclasses must declare a transaction_class")
        return cls.transaction_class

    @classmethod
    @abstractmethod
    def from_header(cls, header: BlockHeader, chaindb: BaseChainDB) -> 'BaseBlock':
        """
        Returns the block denoted by the given block header.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    @property
    @abstractmethod
    def hash(self) -> bytes:
        raise NotImplementedError("Must be implemented by subclasses")

    @property
    @abstractmethod
    def number(self) -> int:
        raise NotImplementedError("Must be implemented by subclasses")

    @property
    def is_genesis(self) -> bool:
        return self.number == 0

    def __repr__(self) -> str:
        return '<{class_name}(#{b})>'.format(
            class_name=self.__class__.__name__,
            b=str(self),
        )

    def __str__(self) -> str:
        return "Block #{b.number}".format(b=self)
