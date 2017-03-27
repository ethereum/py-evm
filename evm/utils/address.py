import rlp

from sha3 import keccak_256

from .numeric import (
    int_to_big_endian,
)
from .padding import (
    pad_left,
)


def force_bytes_to_address(value):
    trimmed_value = value[-20:]
    padded_value = pad_left(trimmed_value, 20, b'\x00')
    return padded_value


def generate_contract_address(address, nonce):
    return keccak_256(rlp.encode([address, nonce])).digest()[12:]
