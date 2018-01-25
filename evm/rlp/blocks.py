import rlp

from evm.utils.datatypes import (
    Configurable,
)


class BaseBlock(rlp.Serializable, Configurable):

    # TODO: Remove this once https://github.com/ethereum/pyrlp/issues/45 is
    # fixed.
    @classmethod
    def get_sedes(cls):
        return rlp.sedes.List(sedes for _, sedes in cls.fields)

    transaction_class = None

    @classmethod
    def get_transaction_class(cls):
        if cls.transaction_class is None:
            raise AttributeError("Block subclasses must declare a transaction_class")
        return cls.transaction_class

    @classmethod
    def from_header(cls, header, chaindb):
        """
        Returns the block denoted by the given block header.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    @property
    def hash(self):
        raise NotImplementedError("Must be implemented by subclasses")

    @property
    def number(self):
        raise NotImplementedError("Must be implemented by subclasses")

    @property
    def is_genesis(self):
        return self.number == 0

    def __repr__(self):
        return '<{class_name}(#{b})>'.format(
            class_name=self.__class__.__name__,
            b=str(self),
        )

    def __str__(self):
        return "Block #{b.number}".format(b=self)
