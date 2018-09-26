try:
    # Python 3.6
    from hashlib import blake2b
except ImportError:
    # Python 3.5
    from pyblake2 import blake2b  # type: ignore


def blake(data: bytes) -> bytes:
    return blake2b(data).digest()[:32]
