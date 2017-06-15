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

    @property
    def hash(self):
        return keccak(rlp.encode(self))

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
