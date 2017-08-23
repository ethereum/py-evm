"""
Functions lifted from https://github.com/vbuterin/pybitcointools
"""
from evm.constants import (
    SECPK1_N as N,
    SECPK1_G as G,
)

from .jacobian import (
    fast_multiply,
)
from .numeric import (
    big_endian_to_int,
    int_to_big_endian,
)
from .padding import (
    pad32,
)


def decode_public_key(public_key):
    if len(public_key) != 64:
        raise ValueError(
            "Unexpected public key format: {}. Public keys must be 64 bytes long and must not "
            "include the fixed \x04 prefix".format(public_key))
    left = big_endian_to_int(public_key[0:32])
    right = big_endian_to_int(public_key[32:64])
    return left, right


def encode_raw_public_key(raw_public_key):
    left, right = raw_public_key
    return b''.join((
        pad32(int_to_big_endian(left)),
        pad32(int_to_big_endian(right)),
    ))


def private_key_to_public_key(private_key):
    if not isinstance(private_key, bytes):
        raise TypeError("`private_key` must be of type `bytes`")
    private_key_as_num = big_endian_to_int(private_key)

    if private_key_as_num >= N:
        raise Exception("Invalid privkey")

    raw_public_key = fast_multiply(G, private_key_as_num)
    public_key = encode_raw_public_key(raw_public_key)
    return public_key
