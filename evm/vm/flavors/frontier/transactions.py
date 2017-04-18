import rlp
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
    validate_canonical_address,
    validate_lt_secpk1n,
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

    def __init__(self, nonce, gas_price, gas, to, value, data, v, r, s):
        validate_uint256(nonce)
        validate_is_integer(gas_price)
        validate_uint256(gas)
        if to != CREATE_CONTRACT_ADDRESS:
            validate_canonical_address(to)
        validate_uint256(value)
        validate_is_bytes(data)

        validate_uint256(v)
        validate_uint256(s)
        validate_uint256(s)
        validate_lt_secpk1n(s)

        super(BaseTransaction, self).__init__(nonce, gas_price, gas, to, value, data, v, r, s)

    def get_sender(self):
        return extract_transaction_sender(self)

    def get_intrensic_gas(self):
        return get_frontier_intrensic_gas(self.data)

    def as_unsigned_transaction(self):
        return FrontierUnsignedTransaction(
            nonce=self.nonce,
            gas_price=self.gas_price,
            gas=self.gas,
            to=self.to,
            value=self.value,
            data=self.data,
        )


class FrontierUnsignedTransaction(rlp.Serializable):
    fields = [
        ('nonce', big_endian_int),
        ('gas_price', big_endian_int),
        ('gas', big_endian_int),
        ('to', address),
        ('value', big_endian_int),
        ('data', binary),
    ]

    def __init__(self, nonce, gas_price, gas, to, value, data):
        validate_uint256(nonce)
        validate_is_integer(gas_price)
        validate_uint256(gas)
        if to != CREATE_CONTRACT_ADDRESS:
            validate_canonical_address(to)
        validate_uint256(value)
        validate_is_bytes(data)

        super(BaseUnsignedTransaction, self).__init__(nonce, gas_price, gas, to, value, data)

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


def get_frontier_intrensic_gas(transaction_data):
    num_zero_bytes = transaction_data.count(b'\x00')
    num_non_zero_bytes = len(transaction_data) - num_zero_bytes
    return (
        GAS_TX +
        num_zero_bytes * GAS_TXDATAZERO +
        num_non_zero_bytes * GAS_TXDATANONZERO
    )
