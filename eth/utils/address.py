import rlp

from eth_hash.auto import keccak
from eth_typing import Address

from eth.utils.numeric import (
    int_to_big_endian,
)


def force_bytes_to_address(value: bytes) -> Address:
    trimmed_value = value[-20:]
    padded_value = trimmed_value.rjust(20, b'\x00')
    return Address(padded_value)


def generate_contract_address(address: Address, nonce: bytes) -> Address:
    return force_bytes_to_address(keccak(rlp.encode([address, nonce])))


def generate_safe_contract_address(address: Address,
                                   salt: int,
                                   call_data: bytes) -> Address:
    return force_bytes_to_address(
        keccak(b'\xff' + address + int_to_big_endian(salt) + keccak(call_data))
    )
