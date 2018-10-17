from eth_typing import Hash32

# This module only supports for Python3.6+, ignore the type hints test for now.
from hashlib import blake2b  # type: ignore


def blake(data: bytes) -> Hash32:
    return Hash32(blake2b(data).digest()[:32])
