import rlp

from evm.db.backends.memory import MemoryDB
from evm.db.chain import BaseChainDB


class BaseBlock(rlp.Serializable):
    db = None

    def __init__(self, header, transactions=None, uncles=None):
        self.db = BaseChainDB(MemoryDB()).db  # for generating transaction_root and receipt_root

        super(BaseBlock, self).__init__(
            header=header,
            transactions=transactions,
            uncles=uncles,
        )

    @classmethod
    def configure(cls, **overrides):
        class_name = cls.__name__
        for key in overrides:
            if not hasattr(cls, key):
                raise TypeError(
                    "The {0}.configure cannot set attributes that are not "
                    "already present on the base class.  The attribute `{1}` was "
                    "not found on the base class `{2}`".format(class_name, key, cls)
                )
        return type(class_name, (cls,), overrides)

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
    def from_header(cls, header, db):
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
