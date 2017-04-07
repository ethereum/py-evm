import rlp

from .keccak import (
    keccak,
)
from .padding import (
    pad_left,
)
from .secp256k1 import (
    private_key_to_public_key,
)


def force_bytes_to_address(value):
    trimmed_value = value[-20:]
    padded_value = pad_left(trimmed_value, 20, b'\x00')
    return padded_value


def generate_contract_address(address, nonce):
    return keccak(rlp.encode([address, nonce]))[-20:]


def private_key_to_address(private_key):
    public_key = private_key_to_public_key(private_key)
    return public_key_to_address(public_key)


def public_key_to_address(public_key):
    return keccak(public_key[1:])[-20:]
