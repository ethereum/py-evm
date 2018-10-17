from eth_typing import Hash32

# This module only supports for Python3.6+
from hashlib import blake2b


def blake(data: bytes) -> Hash32:
    return Hash32(blake2b(data).digest()[:32])
