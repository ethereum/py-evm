from hashlib import blake2b


def blake(data: bytes) -> bytes:
    return blake2b(data).digest()[:32]
