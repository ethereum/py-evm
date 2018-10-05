# This module only supports for Python3.6+, ignore the type hints test for now.
from hashlib import blake2b  # type: ignore


def blake(data: bytes) -> bytes:
    return blake2b(data).digest()[:32]
