import rlp

from evm.utils.keccak import (
    keccak,
)


class BaseBlock(rlp.Serializable):
    db = None

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

    transaction_class = None

    @classmethod
    def get_transaction_class(cls):
        if cls.transaction_class is None:
            raise AttributeError("OpenBlock subclasses must declare a transaction_class")
        return cls.transaction_class

    @classmethod
    def from_header(cls, header):
        """
        Returns the block denoted by the given block header.
        """
        raise NotImplementedError(
            "The `Block.from_header` class method must be implemented by subclasses."
        )

    def get_parent_header(self):
        """
        Returns the header for the parent block.
        """
        raise NotImplementedError("`Block.get_parent` must be implemented by subclasses")

    def get_parent(self):
        """
        Returns the parent block.
        """
        raise NotImplementedError("`Block.get_parent` must be implemented by subclasses")

    @property
    def hash(self):
        return keccak(rlp.encode(self))

    @property
    def number(self):
        raise NotImplementedError("`Block.number` must be implemented by subclasses")

    @property
    def is_genesis(self):
        return self.number == 0

    def validate(self):
        pass

    def apply_transaction(self, evm, transaction):
        """
        Applies the given transaction to the current block.
        """
        raise NotImplementedError(
            "The `Block.apply_transaction` method must be implemented by subclasses"
        )

    def mine(self, *args, **kwargs):
        """
        Mines the block.
        """
        raise NotImplementedError("The `Block.mine` method must be implemented by subclasses")

    def __repr__(self):
        return '<{class_name}(#{b})>'.format(
            class_name=self.__class__.__name__,
            b=str(self),
        )

    def __str__(self):
        return "Block #{b.number}".format(b=self)
