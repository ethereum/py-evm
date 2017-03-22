import rlp

from eth_utils import (
    pad_left,
    to_canonical_address,
    keccak,
)

from .numeric import (
    int_to_big_endian,
)


def force_bytes_to_address(value):
    address = pad_left(value[-20:], 20, b'\x00')
    return address


def generate_contract_address(address, nonce):
    return keccak(rlp.encode([to_canonical_address(address), nonce]))[12:]
