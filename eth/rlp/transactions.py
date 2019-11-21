from cached_property import cached_property
import rlp
from rlp.sedes import (
    big_endian_int,
    binary,
)

from eth_typing import (
    Address
)

from eth_hash.auto import keccak
from eth_utils import (
    ValidationError,
)

from eth.abc import (
    BaseTransactionAPI,
    ComputationAPI,
    SignedTransactionAPI,
    TransactionFieldsAPI,
    UnsignedTransactionAPI,
)

from .sedes import address


class BaseTransactionMethods(BaseTransactionAPI):
    def validate(self) -> None:
        pass

    @property
    def intrinsic_gas(self) -> int:
        return self.get_intrinsic_gas()

    def gas_used_by(self, computation: ComputationAPI) -> int:
        return self.get_intrinsic_gas() + computation.get_gas_used()


BASE_TRANSACTION_FIELDS = [
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


class BaseTransactionFields(rlp.Serializable, TransactionFieldsAPI):
    fields = BASE_TRANSACTION_FIELDS

    @property
    def hash(self) -> bytes:
        return keccak(rlp.encode(self))


class BaseTransaction(BaseTransactionFields, BaseTransactionMethods, SignedTransactionAPI):  # noqa: E501
    # this is duplicated to make the rlp library happy, otherwise it complains
    # about no fields being defined but inheriting from multiple `Serializable`
    # bases.
    fields = BASE_TRANSACTION_FIELDS

    @classmethod
    def from_base_transaction(cls, transaction: SignedTransactionAPI) -> SignedTransactionAPI:
        return rlp.decode(rlp.encode(transaction), sedes=cls)

    @cached_property
    def sender(self) -> Address:
        return self.get_sender()

    # +-------------------------------------------------------------+
    # | API that must be implemented by all Transaction subclasses. |
    # +-------------------------------------------------------------+

    #
    # Validation
    #
    def validate(self) -> None:
        if self.gas < self.intrinsic_gas:
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


class BaseUnsignedTransaction(BaseTransactionMethods, UnsignedTransactionAPI):
    fields = [
        ('nonce', big_endian_int),
        ('gas_price', big_endian_int),
        ('gas', big_endian_int),
        ('to', address),
        ('value', big_endian_int),
        ('data', binary),
    ]
