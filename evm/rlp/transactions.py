import rlp

from evm.exceptions import (
    ValidationError,
)

from evm.utils.keccak import (
    keccak,
)


class BaseTransaction(rlp.Serializable):
    def __init__(self, *args, **kwargs):
        super(BaseTransaction, self).__init__(*args, **kwargs)
        if not self.fields:
            raise TypeError("Subclasses of `BaseTransaction` must declare `fields`")

    @property
    def hash(self):
        return keccak(rlp.encode(self))

    @property
    def sender(self):
        """
        Convenience property for the return value of `get_sender`
        """
        return self.get_sender()

    @property
    def intrensic_gas(self):
        """
        Convenience property for the return value of `get_intrensic_gas`
        """
        return self.get_intrensic_gas()

    # +-------------------------------------------------------------+
    # | API that must be implemented by all Transaction subclasses. |
    # +-------------------------------------------------------------+

    #
    # Validation
    #
    def validate(self):
        """
        Hook called during instantiation to ensure that all transaction
        parameters pass validation rules.
        """
        if self.intrensic_gas > self.gas:
            raise ValidationError("Insufficient gas")
        self.check_signature_validity()

    #
    # Signature and Sender
    #
    @property
    def is_signature_valid(self):
        try:
            self.check_signature_validity()
        except ValidationError:
            return False
        else:
            return True

    def check_signature_validity(self):
        """
        Checks signature validity, raising a ValidationError if the signature
        is invalid.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def get_sender(self):
        """
        Get the 20-byte address which sent this transaction.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # Base gas costs
    #
    def get_intrensic_gas(self):
        """
        Compute the baseline gas cost for this transaction.  This is the amount
        of gas needed to send this transaction (but that is not actually used
        for computation).
        """
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # Conversion to and creation of unsigned transactions.
    #
    def as_unsigned_transaction(self):
        """
        Return an unsigned version of this transaction.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    @classmethod
    def create_unsigned_transaction(self, *args, **kwargs):
        """
        Create an unsigned transaction.
        """
        raise NotImplementedError("Must be implemented by subclasses")


class BaseUnsignedTransaction(rlp.Serializable):
    def __init__(self, *args, **kwargs):
        super(BaseUnsignedTransaction, self).__init__(*args, **kwargs)
        if not self.fields:
            raise TypeError("Subclasses of `BaseUnsignedTransaction` must declare `fields`")

    #
    # API that must be implemented by all Transaction subclasses.
    #
    def validate(self):
        """
        Hook called during instantiation to ensure that all transaction
        parameters pass validation rules.
        """
        pass

    def as_signed_transaction(self, private_key):
        """
        Return a version of this transaction which has been signed using the
        provided `private_key`
        """
        raise NotImplementedError("Must be implemented by subclasses")
