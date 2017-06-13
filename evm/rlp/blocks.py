import rlp


class BaseBlock(rlp.Serializable):
    transaction_class = None

    @classmethod
    def get_transaction_class(cls):
        if cls.transaction_class is None:
            raise AttributeError("OpenBlock subclasses must declare a transaction_class")
        return cls.transaction_class

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
