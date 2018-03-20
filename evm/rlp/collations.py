from abc import (
    ABCMeta,
    abstractmethod
)
from typing import Type

import rlp

from evm.utils.datatypes import (
    Configurable,
)

from evm.db.chain import BaseChainDB

from .transactions import BaseShardingTransaction
from .headers import CollationHeader


class BaseCollation(rlp.Serializable, Configurable, metaclass=ABCMeta):

    # TODO: Remove this once https://github.com/ethereum/pyrlp/issues/45 is
    # fixed.
    @classmethod
    def get_sedes(cls):
        return rlp.sedes.List(sedes for _, sedes in cls.fields)

    transaction_class = None  # type: Type[BaseShardingTransaction]

    @classmethod
    def get_transaction_class(cls) -> Type[BaseShardingTransaction]:
        if cls.transaction_class is None:
            raise AttributeError("Collation subclasses must declare a transaction_class")
        return cls.transaction_class

    @classmethod
    @abstractmethod
    def from_header(cls, header: CollationHeader, chaindb: BaseChainDB) -> 'BaseCollation':
        """
        Returns the collation denoted by the given collation header.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    @property
    @abstractmethod
    def hash(self) -> bytes:
        raise NotImplementedError("Must be implemented by subclasses")

    @property
    @abstractmethod
    def shard_id(self) -> int:
        raise NotImplementedError("Must be implemented by subclasses")

    @property
    @abstractmethod
    def expected_period_number(self) -> int:
        raise NotImplementedError("Must be implemented by subclasses")

    @property
    @abstractmethod
    def number(self) -> int:
        raise NotImplementedError("Must be implemented by subclasses")

    def __repr__(self) -> str:
        return '<{class_name}(#{b})>'.format(
            class_name=self.__class__.__name__,
            b=str(self),
        )

    def __str__(self) -> str:
        return "Collation #{b.expected_period_number} (shard #{b.header.shard_id})".format(b=self)
