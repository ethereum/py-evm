import rlp

from eth_hash.auto import keccak
from eth_typing import Address

def force_bytes_to_address(value: bytes) -> Address:
    trimmed_value = value[-20:]
    padded_value = trimmed_value.rjust(20, b'\x00')
    return Address(padded_value)


def generate_contract_address(address: Address, nonce: bytes) -> Address:
    return Address(keccak(rlp.encode([address, nonce]))[-20:])
