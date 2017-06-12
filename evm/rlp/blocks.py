import rlp


class BaseBlock(rlp.Serializable):
    @property
    def is_sealed(self):
        return not self.is_open


class BaseOpenBlock(BaseBlock):
    is_open = True

    transaction_class = None

    @classmethod
    def get_transaction_class(cls):
        if cls.transaction_class is None:
            raise AttributeError("OpenBlock subclasses must declare a transaction_class")
        return cls.transaction_class

    sealed_block_class = None

    @classmethod
    def get_sealed_block_class(cls):
        if cls.sealed_block_class is None:
            raise AttributeError("OpenBlock subclasses must declare a sealed_block_class")
        return cls.sealed_block_class


class BaseSealedBlock(BaseBlock):
    is_open = False
