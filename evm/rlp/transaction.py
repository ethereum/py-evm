# -*- coding: utf-8 -*-
import rlp
from rlp.sedes import big_endian_int, binary

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

    """
    A transaction is stored as:
    [nonce, gasprice, startgas, to, value, data, v, r, s]

    nonce is the number of transactions already sent by that account, encoded
    in binary form (eg.  0 -> '', 7 -> '\x07', 1000 -> '\x03\xd8').

    (v,r,s) is the raw Electrum-style signature of the transaction without the
    signature made with the private key corresponding to the sending account,
    with 0 <= v <= 3. From an Electrum-style signature (65 bytes) it is
    possible to extract the public key, and thereby the address, directly.

    A valid transaction is one where:
    (i) the signature is well-formed (ie. 0 <= v <= 3, 0 <= r < P, 0 <= s < N,
        0 <= r < P - N if v >= 2), and
    (ii) the sending account has enough funds to pay the fee and the value.
    """

    fields = [
        ('nonce', big_endian_int),
        ('gasprice', big_endian_int),
        ('startgas', big_endian_int),
        ('to', address),
        ('value', big_endian_int),
        ('data', binary),
        ('v', big_endian_int),
        ('r', big_endian_int),
        ('s', big_endian_int),
    ]

    _sender = None

    def __init__(self, nonce, gasprice, startgas, to, value, data, v, r, s):
        validate_uint256(nonce)
        validate_is_integer(gasprice)
        validate_uint256(startgas)
        validate_canonical_address(to)
        validate_uint256(value)
        validate_is_bytes(data)

        validate_uint256(v)
        validate_uint256(s)
        validate_lt_secpk1n(s)
        validate_uint256(s)


UnsignedTransaction = Transaction.exclude(['v', 'r', 's'])
