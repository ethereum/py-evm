from eth_typing import (
    Hash32,
)


def bitwise_xor(a: Hash32, b: Hash32) -> Hash32:
    """
    Return the xor of hash ``a`` and hash ``b``
    """

    result = bytes(bit_a ^ bit_b for bit_a, bit_b in zip(a, b))
    return Hash32(result)


def is_power_of_two(value: int) -> bool:
    """
    Check if ``value`` is a power of two integer.
    """
    if value == 0:
        return False
    else:
        return bool(value and not (value & (value - 1)))
