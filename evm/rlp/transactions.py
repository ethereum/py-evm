import rlp
from rlp.sedes import (
    big_endian_int,
    binary,
)

from eth_utils import (
    keccak,
)

from evm.exceptions import (
    ValidationError,
)

from evm.rlp.sedes import (
    address,
    access_list as access_list_sedes,
    hash32,
)
from evm.utils.state_access_restriction import (
    to_prefix_list_form,
)


class BaseTransaction(rlp.Serializable):
    fields = [
        ('nonce', big_endian_int),
        ('gas_price', big_endian_int),
        ('gas', big_endian_int),
        ('to', address),
        ('value', big_endian_int),
        ('data', binary),
        ('v', big_endian_int),
        ('r', big_endian_int),
        ('s', big_endian_int),
    ]

    @classmethod
    def from_base_transaction(cls, transaction):
        return rlp.decode(rlp.encode(transaction), sedes=cls)

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
    def intrinsic_gas(self):
        """
        Convenience property for the return value of `get_intrinsic_gas`
        """
        return self.get_intrinsic_gas()

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
        if self.intrinsic_gas > self.gas:
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
    # Get gas costs
    #
    def get_intrinsic_gas(self):
        """
        Compute the baseline gas cost for this transaction.  This is the amount
        of gas needed to send this transaction (but that is not actually used
        for computation).
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def gas_used_by(self, computation):
        """
        Return the gas used by the given computation. In Frontier,
        for example, this is sum of the intrinsic cost and the gas used
        during computation.
        """
        return self.get_intrinsic_gas() + computation.get_gas_used()

    #
    # Conversion to and creation of unsigned transactions.
    #
    def get_message_for_signing(self):
        """
        Return the bytestring that should be signed in order to create a signed transactions
        """
        raise NotImplementedError("Must be implemented by subclasses")

    @classmethod
    def create_unsigned_transaction(self, *args, **kwargs):
        """
        Create an unsigned transaction.
        """
        raise NotImplementedError("Must be implemented by subclasses")


class BaseUnsignedTransaction(rlp.Serializable):
    fields = [
        ('nonce', big_endian_int),
        ('gas_price', big_endian_int),
        ('gas', big_endian_int),
        ('to', address),
        ('value', big_endian_int),
        ('data', binary),
    ]

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


class BaseShardingTransaction(rlp.Serializable):
    fields = [
        ('chain_id', big_endian_int),
        ('shard_id', big_endian_int),
        ('to', address),
        ('data', binary),
        ('gas', big_endian_int),
        ('access_list', access_list_sedes),
        ('code', binary),
        ('salt', hash32),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prefix_list = to_prefix_list_form(self.access_list)

    @property
    def hash(self):
        return keccak(rlp.encode(self))

    @property
    def sig_hash(self):
        sedes = self.__class__.exclude('data')
        return keccak(rlp.encode(self, sedes))

    #
    # Validation
    #
    def validate(self):
        """
        Hook called during instantiation to ensure that all transaction
        parameters pass validation rules.
        """
        if self.intrinsic_gas > self.gas:
            raise ValidationError("Insufficient gas")

    @property
    def intrinsic_gas(self):
        """
        Convenience property for the return value of `get_intrinsic_gas`
        """
        return self.get_intrinsic_gas()

    #
    # Base gas costs
    #
    def get_intrinsic_gas(self):
        """
        Compute the baseline gas cost for this transaction.  This is the amount
        of gas needed to send this transaction (but that is not actually used
        for computation).
        """
        raise NotImplementedError("Must be implemented by subclasses")
