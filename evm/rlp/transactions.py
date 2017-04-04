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

from evm.utils.address import (
    public_key_to_address,
)
from evm.utils.ecdsa import (
    ecdsa_sign,
    decode_signature,
    encode_signature,
    ecdsa_recover,
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
        validate_uint256(s)
        validate_lt_secpk1n(s)

        super(Transaction, self).__init__(nonce, gas_price, gas, to, value, data, v, r, s)

    @property
    def sender(self):
        return extract_transaction_sender(self)


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


def sign_transaction(unsigned_txn, private_key):
    signature = ecdsa_sign(rlp.encode(unsigned_txn), private_key)
    v, r, s = decode_signature(signature)
    return Transaction(
        nonce=unsigned_txn.nonce,
        gas_price=unsigned_txn.gas_price,
        gas=unsigned_txn.gas,
        to=unsigned_txn.to,
        value=unsigned_txn.value,
        data=unsigned_txn.data,
        v=v,
        r=r,
        s=s,
    )


def extract_transaction_sender(transaction):
    unsigned_transaction = UnsignedTransaction(
        nonce=transaction.nonce,
        gas_price=transaction.gas_price,
        gas=transaction.gas,
        to=transaction.to,
        value=transaction.value,
        data=transaction.data,
    )
    signature = encode_signature(
        v=transaction.v,
        r=transaction.r,
        s=transaction.s,
    )
    public_key = ecdsa_recover(rlp.encode(unsigned_transaction), signature)
    sender = public_key_to_address(public_key)
    return sender
