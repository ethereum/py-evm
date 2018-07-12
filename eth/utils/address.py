import rlp

from eth_hash.auto import keccak


def force_bytes_to_address(value: bytes) -> bytes:
    trimmed_value = value[-20:]
    padded_value = trimmed_value.rjust(20, b'\x00')
    return padded_value


def generate_contract_address(address: bytes, nonce: bytes) -> bytes:
    return keccak(rlp.encode([address, nonce]))[-20:]
