import rlp


class BaseCollation(rlp.Serializable):
    db = None

    transaction_class = None

    @classmethod
    def get_transaction_class(cls):
        if cls.transaction_class is None:
            raise AttributeError("Collation subclasses must declare a transaction_class")
        return cls.transaction_class

    @classmethod
    def from_header(cls, header, db):
        """
        Returns the block denoted by the given block header.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def get_parent_header(self):
        """
        Returns the header for the parent block.
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

    def validate(self):
        pass

    def add_transaction(self, transaction, computation):
        """
        Adds the given transaction to the current block.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def __repr__(self):
        return '<{class_name}(#{b})>'.format(
            class_name=self.__class__.__name__,
            b=str(self),
        )

    def __str__(self):
        return "Collation #{b.number}".format(b=self)
