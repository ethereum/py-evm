from eth_typing import (
    Hash32,
)


def bitwise_xor(a: Hash32, b: Hash32) -> Hash32:
    """
    Return the xor of hash ``a`` and hash ``b``
    """

    result = bytes(bit_a ^ bit_b for bit_a, bit_b in zip(a, b))
    return Hash32(result)
