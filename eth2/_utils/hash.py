from hashlib import sha256
from typing import (
    Union,
)

from eth_typing import Hash32


def hash_eth2(data: Union[bytes, bytearray]) -> Hash32:
    """
    Return SHA-256 hash of ``data``.
    Note: it's a placeholder and we aim to migrate to a S[T/N]ARK-friendly hash function in
    a future Ethereum 2.0 deployment phase.
    """
    return Hash32(sha256(data).digest())
