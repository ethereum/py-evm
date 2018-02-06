import rlp

from cytoolz import memoize
import lru

from .keccak import (
    keccak,
)
from .padding import (
    pad_left,
)


@memoize(cache=lru.LRU(64))
def force_bytes_to_address(value):
    trimmed_value = value[-20:]
    padded_value = pad_left(trimmed_value, 20, b'\x00')
    return padded_value


def generate_contract_address(address, nonce):
    return keccak(rlp.encode([address, nonce]))[-20:]
