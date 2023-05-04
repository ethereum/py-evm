from eth_utils.toolz import (
    curry,
)

from eth import (
    constants,
)
from eth._utils.numeric import (
    ceil8,
    signed_to_unsigned,
    unsigned_to_signed,
)
from eth.abc import (
    ComputationAPI,
)


def add(computation: ComputationAPI) -> None:
    """
    Addition
    """
    left, right = computation.stack_pop_ints(2)

    result = (left + right) & constants.UINT_256_MAX

    computation.stack_push_int(result)


def addmod(computation: ComputationAPI) -> None:
    """
    Modulo Addition
    """
    left, right, mod = computation.stack_pop_ints(3)

    if mod == 0:
        result = 0
    else:
        result = (left + right) % mod

    computation.stack_push_int(result)


def sub(computation: ComputationAPI) -> None:
    """
    Subtraction
    """
    left, right = computation.stack_pop_ints(2)

    result = (left - right) & constants.UINT_256_MAX

    computation.stack_push_int(result)


def mod(computation: ComputationAPI) -> None:
    """
    Modulo
    """
    value, mod = computation.stack_pop_ints(2)

    if mod == 0:
        result = 0
    else:
        result = value % mod

    computation.stack_push_int(result)


def smod(computation: ComputationAPI) -> None:
    """
    Signed Modulo
    """
    value, mod = map(
        unsigned_to_signed,
        computation.stack_pop_ints(2),
    )

    pos_or_neg = -1 if value < 0 else 1

    if mod == 0:
        result = 0
    else:
        result = (abs(value) % abs(mod) * pos_or_neg) & constants.UINT_256_MAX

    computation.stack_push_int(signed_to_unsigned(result))


def mul(computation: ComputationAPI) -> None:
    """
    Multiplication
    """
    left, right = computation.stack_pop_ints(2)

    result = (left * right) & constants.UINT_256_MAX

    computation.stack_push_int(result)


def mulmod(computation: ComputationAPI) -> None:
    """
    Modulo Multiplication
    """
    left, right, mod = computation.stack_pop_ints(3)

    if mod == 0:
        result = 0
    else:
        result = (left * right) % mod
    computation.stack_push_int(result)


def div(computation: ComputationAPI) -> None:
    """
    Division
    """
    numerator, denominator = computation.stack_pop_ints(2)

    if denominator == 0:
        result = 0
    else:
        result = (numerator // denominator) & constants.UINT_256_MAX

    computation.stack_push_int(result)


def sdiv(computation: ComputationAPI) -> None:
    """
    Signed Division
    """
    numerator, denominator = map(
        unsigned_to_signed,
        computation.stack_pop_ints(2),
    )

    pos_or_neg = -1 if numerator * denominator < 0 else 1

    if denominator == 0:
        result = 0
    else:
        result = (pos_or_neg * (abs(numerator) // abs(denominator)))

    computation.stack_push_int(signed_to_unsigned(result))


@curry
def exp(computation: ComputationAPI, gas_per_byte: int) -> None:
    """
    Exponentiation
    """
    base, exponent = computation.stack_pop_ints(2)

    bit_size = exponent.bit_length()
    byte_size = ceil8(bit_size) // 8

    if exponent == 0:
        result = 1
    elif base == 0:
        result = 0
    else:
        result = pow(base, exponent, constants.UINT_256_CEILING)

    computation.consume_gas(
        gas_per_byte * byte_size,
        reason="EXP: exponent bytes",
    )

    computation.stack_push_int(result)


def signextend(computation: ComputationAPI) -> None:
    """
    Signed Extend
    """
    bits, value = computation.stack_pop_ints(2)

    if bits <= 31:
        testbit = bits * 8 + 7
        sign_bit = (1 << testbit)
        if value & sign_bit:
            result = value | (constants.UINT_256_CEILING - sign_bit)
        else:
            result = value & (sign_bit - 1)
    else:
        result = value

    computation.stack_push_int(result)


def shl(computation: ComputationAPI) -> None:
    """
    Bitwise left shift
    """
    shift_length, value = computation.stack_pop_ints(2)

    if shift_length >= 256:
        result = 0
    else:
        result = (value << shift_length) & constants.UINT_256_MAX

    computation.stack_push_int(result)


def shr(computation: ComputationAPI) -> None:
    """
    Bitwise right shift
    """
    shift_length, value = computation.stack_pop_ints(2)

    if shift_length >= 256:
        result = 0
    else:
        result = (value >> shift_length) & constants.UINT_256_MAX

    computation.stack_push_int(result)


def sar(computation: ComputationAPI) -> None:
    """
    Arithmetic bitwise right shift
    """
    shift_length, value = computation.stack_pop_ints(2)
    value = unsigned_to_signed(value)

    if shift_length >= 256:
        result = 0 if value >= 0 else constants.UINT_255_NEGATIVE_ONE
    else:
        result = (value >> shift_length) & constants.UINT_256_MAX

    computation.stack_push_int(result)
