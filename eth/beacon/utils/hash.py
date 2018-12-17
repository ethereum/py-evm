from eth_typing import Hash32
from eth_hash.auto import keccak


def hash_eth2(data: bytes) -> Hash32:
    return Hash32(keccak(data))
