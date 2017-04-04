import rlp
from rlp.sedes import (
    big_endian_int,
    binary,
)

from evm.validation import (
    validate_uint256,
    validate_is_integer,
    validate_is_bytes,
    validate_canonical_address,
    validate_lt_secpk1n,
)

from .sedes import (
    address,
)


class Transaction(rlp.Serializable):
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
        validate_canonical_address(to)
        validate_uint256(value)
        validate_is_bytes(data)

        validate_uint256(v)
        validate_uint256(s)
        validate_lt_secpk1n(s)
        validate_uint256(s)

        super(Transaction, self).__init__(nonce, gas_price, gas, to, value, data, v, r, s)


class UnsignedTransaction(rlp.Serializable):
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
        validate_canonical_address(to)
        validate_uint256(value)
        validate_is_bytes(data)

        super(UnsignedTransaction, self).__init__(nonce, gas_price, gas, to, value, data)
