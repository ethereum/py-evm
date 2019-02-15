import decimal

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


def integer_squareroot(value: int) -> int:
    """
    Return the integer square root of ``value``.
    Uses Python's decimal module to compute the square root of ``value`` with
    a precision of 128-bits. The value 128 is chosen since the largest square
    root of a 256-bit integer is a 128-bit integer.
    """
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(
            "Value must be an integer: Got: {0}".format(
                type(value),
            )
        )
    if value < 0:
        raise ValueError(
            "Value cannot be negative: Got: {0}".format(
                value,
            )
        )

    with decimal.localcontext() as ctx:
        ctx.prec = 128
        return int(decimal.Decimal(value).sqrt())
