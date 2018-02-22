import rlp

from eth_utils import (
    keccak,
)


def force_bytes_to_address(value):
    trimmed_value = value[-20:]
    padded_value = trimmed_value.rjust(20, b'\x00')
    return padded_value


def generate_contract_address(address, nonce):
    return keccak(rlp.encode([address, nonce]))[-20:]
