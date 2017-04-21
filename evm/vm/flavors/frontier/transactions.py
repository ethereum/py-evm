from rlp.sedes import (
    big_endian_int,
    binary,
)

from evm.constants import (
    GAS_TX,
    GAS_TXDATAZERO,
    GAS_TXDATANONZERO,
    CREATE_CONTRACT_ADDRESS,
)
from evm.validation import (
    validate_uint256,
    validate_is_integer,
    validate_is_bytes,
    validate_lt_secpk1n,
    validate_lte,
    validate_gte,
    validate_canonical_address,
)

from evm.rlp.transactions import (
    BaseTransaction,
    BaseUnsignedTransaction,
)
from evm.rlp.sedes import (
    address,
)

from evm.utils.transactions import (
    create_transaction_signature,
    extract_transaction_sender,
    validate_transaction_signature,
)


class FrontierTransaction(BaseTransaction):
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

    def validate(self):
        validate_uint256(self.nonce)
        validate_uint256(self.gas_price)
        validate_uint256(self.gas)
        if self.to != CREATE_CONTRACT_ADDRESS:
            validate_canonical_address(self.to)
        validate_uint256(self.value)
        validate_is_bytes(self.data)

        validate_uint256(self.v)
        validate_uint256(self.r)
        validate_uint256(self.s)

        validate_lt_secpk1n(self.r)
        validate_gte(self.r, minimum=1)
        validate_lt_secpk1n(self.s)
        validate_gte(self.s, minimum=1)

        validate_gte(self.v, minimum=27)
        validate_lte(self.v, maximum=28)

        super(FrontierTransaction, self).validate()

    def check_signature_validity(self):
        validate_transaction_signature(self)

    def get_sender(self):
        return extract_transaction_sender(self)

    def get_intrensic_gas(self):
        return _get_frontier_intrensic_gas(self.data)

    def as_unsigned_transaction(self):
        return FrontierUnsignedTransaction(
            nonce=self.nonce,
            gas_price=self.gas_price,
            gas=self.gas,
            to=self.to,
            value=self.value,
            data=self.data,
        )

    @classmethod
    def create_unsigned_transaction(cls, nonce, gas_price, gas, to, value, data):
        return FrontierUnsignedTransaction(nonce, gas_price, gas, to, value, data)


class FrontierUnsignedTransaction(BaseUnsignedTransaction):
    fields = [
        ('nonce', big_endian_int),
        ('gas_price', big_endian_int),
        ('gas', big_endian_int),
        ('to', address),
        ('value', big_endian_int),
        ('data', binary),
    ]

    def validate(self):
        validate_uint256(self.nonce)
        validate_is_integer(self.gas_price)
        validate_uint256(self.gas)
        if self.to != CREATE_CONTRACT_ADDRESS:
            validate_canonical_address(self.to)
        validate_uint256(self.value)
        validate_is_bytes(self.data)
        super(FrontierUnsignedTransaction, self).validate()

    def as_signed_transaction(self, private_key):
        v, r, s = create_transaction_signature(self, private_key)
        return FrontierTransaction(
            nonce=self.nonce,
            gas_price=self.gas_price,
            gas=self.gas,
            to=self.to,
            value=self.value,
            data=self.data,
            v=v,
            r=r,
            s=s,
        )


def _get_frontier_intrensic_gas(transaction_data):
    num_zero_bytes = transaction_data.count(b'\x00')
    num_non_zero_bytes = len(transaction_data) - num_zero_bytes
    return (
        GAS_TX +
        num_zero_bytes * GAS_TXDATAZERO +
        num_non_zero_bytes * GAS_TXDATANONZERO
    )
