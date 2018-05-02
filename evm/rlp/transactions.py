from abc import (
    ABCMeta,
    abstractmethod
)
from typing import (
    Any,
)

import rlp
from rlp.sedes import (
    big_endian_int,
    binary,
)

from eth_typing import (
    Address
)

from eth_hash.auto import keccak

from evm.exceptions import (
    ValidationError,
)

from evm.rlp.sedes import (
    address,
)

from evm.vm.computation import (
    BaseComputation
)


class BaseTransactionCommonMethods:
    def validate(self) -> None:
        """
        Hook called during instantiation to ensure that all transaction
        parameters pass validation rules.
        """
        pass

    @property
    def intrinsic_gas(self) -> int:
        """
        Convenience property for the return value of `get_intrinsic_gas`
        """
        return self.get_intrinsic_gas()

    @abstractmethod
    def get_intrinsic_gas(self) -> int:
        """
        Compute the baseline gas cost for this transaction.  This is the amount
        of gas needed to send this transaction (but that is not actually used
        for computation).
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def gas_used_by(self, computation: BaseComputation) -> int:
        """
        Return the gas used by the given computation. In Frontier,
        for example, this is sum of the intrinsic cost and the gas used
        during computation.
        """
        return self.get_intrinsic_gas() + computation.get_gas_used()


class BaseTransaction(rlp.Serializable, BaseTransactionCommonMethods):
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
    def from_base_transaction(cls, transaction: 'BaseTransaction') -> 'BaseTransaction':
        return rlp.decode(rlp.encode(transaction), sedes=cls)

    @property
    def hash(self) -> bytes:
        return keccak(rlp.encode(self))

    @property
    def sender(self) -> Address:
        """
        Convenience property for the return value of `get_sender`
        """
        return self.get_sender()

    # +-------------------------------------------------------------+
    # | API that must be implemented by all Transaction subclasses. |
    # +-------------------------------------------------------------+

    #
    # Validation
    #
    def validate(self) -> None:
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
    def is_signature_valid(self) -> bool:
        try:
            self.check_signature_validity()
        except ValidationError:
            return False
        else:
            return True

    @abstractmethod
    def check_signature_validity(self) -> None:
        """
        Checks signature validity, raising a ValidationError if the signature
        is invalid.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    def get_sender(self) -> Address:
        """
        Get the 20-byte address which sent this transaction.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # Conversion to and creation of unsigned transactions.
    #
    @abstractmethod
    def get_message_for_signing(self) -> bytes:
        """
        Return the bytestring that should be signed in order to create a signed transactions
        """
        raise NotImplementedError("Must be implemented by subclasses")

    @classmethod
    @abstractmethod
    def create_unsigned_transaction(self, *args: Any, **kwargs: Any) -> 'BaseTransaction':
        """
        Create an unsigned transaction.
        """
        raise NotImplementedError("Must be implemented by subclasses")


class BaseUnsignedTransaction(rlp.Serializable, BaseTransactionCommonMethods, metaclass=ABCMeta):
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
    @abstractmethod
    def as_signed_transaction(self, private_key: bytes) -> 'BaseTransaction':
        """
        Return a version of this transaction which has been signed using the
        provided `private_key`
        """
        raise NotImplementedError("Must be implemented by subclasses")
