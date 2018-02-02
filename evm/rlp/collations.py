import rlp


class BaseCollation(rlp.Serializable):
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
            raise AttributeError("Collation subclasses must declare a transaction_class")
        return cls.transaction_class

    @classmethod
    def from_header(cls, header, chaindb):
        """
        Returns the collation denoted by the given collation header.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    @property
    def hash(self):
        raise NotImplementedError("Must be implemented by subclasses")

    @property
    def shard_id(self):
        raise NotImplementedError("Must be implemented by subclasses")

    @property
    def expected_period_number(self):
        raise NotImplementedError("Must be implemented by subclasses")

    def __repr__(self):
        return '<{class_name}(#{b})>'.format(
            class_name=self.__class__.__name__,
            b=str(self),
        )

    def __str__(self):
        return "Collation #{b.expected_period_number} (shard #{b.header.shard_id})".format(b=self)
