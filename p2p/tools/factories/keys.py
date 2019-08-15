import secrets

from eth_utils import (
    keccak,
    int_to_big_endian,
)

from eth_keys import keys


def PrivateKeyFactory(seed: bytes=None) -> keys.PrivateKey:
    if seed is None:
        key_bytes = int_to_big_endian(secrets.randbits(256)).rjust(32, b'\x00')
    else:
        key_bytes = keccak(seed)
    return keys.PrivateKey(key_bytes)


def PublicKeyFactory() -> keys.PublicKey:
    return PrivateKeyFactory().public_key
