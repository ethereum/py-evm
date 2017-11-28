import rlp


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

    def mine(self, *args, **kwargs):
        """
        Mines the block.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def __repr__(self):
        return '<{class_name}(#{b})>'.format(
            class_name=self.__class__.__name__,
            b=str(self),
        )

    def __str__(self):
        return "Block #{b.number}".format(b=self)
