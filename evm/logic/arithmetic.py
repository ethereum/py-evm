import logging

from evm.constants import (
    UINT_256_MAX,
    UINT_256_CEILING,
)
from evm.gas import (
    COST_VERYLOW,
    COST_LOW,
    COST_MID,
    COST_EXP,
    COST_EXPBYTE,
)

from evm.utils.numeric import (
    big_endian_to_int,
    int_to_big_endian,
    unsigned_to_signed,
    signed_to_unsigned,
    ceil8,
)


logger = logging.getLogger('evm.logic.arithmetic')


def add(message, storage, state):
    """
    Addition
    """
    left = big_endian_to_int(state.stack.pop())
    right = big_endian_to_int(state.stack.pop())
    result = (left + right) & UINT_256_MAX
    logger.info('ADD: %s + %s -> %s', left, right, result)
    state.stack.push(
        int_to_big_endian(result)
    )
    state.consume_gas(COST_VERYLOW)


def addmod(message, storage, state):
    """
    Modulo Addition
    """
    left = big_endian_to_int(state.stack.pop())
    right = big_endian_to_int(state.stack.pop())
    mod = big_endian_to_int(state.stack.pop())

    if mod == 0:
        result = 0
    else:
        result = (left + right) % mod
    logger.info('ADDMOD: (%s + %s) %% %s -> %s', left, right, mod, result)
    state.stack.push(
        int_to_big_endian(result)
    )
    state.consume_gas(COST_MID)


def sub(message, storage, state):
    """
    Subtraction
    """
    left = big_endian_to_int(state.stack.pop())
    right = big_endian_to_int(state.stack.pop())
    result = (left - right) & UINT_256_MAX
    logger.info('SUB: %s + %s -> %s', left, right, result)
    state.stack.push(
        int_to_big_endian(result)
    )
    state.consume_gas(COST_VERYLOW)


def mod(message, storage, state):
    """
    Modulo
    """
    value = big_endian_to_int(state.stack.pop())
    mod = big_endian_to_int(state.stack.pop())

    if mod == 0:
        result = 0
    else:
        result = value % mod

    logger.info('MOD: %s %% %s -> %s', value, mod, result)
    state.stack.push(
        int_to_big_endian(result)
    )
    state.consume_gas(COST_LOW)


def smod(message, storage, state):
    """
    Signed Modulo
    """
    value = unsigned_to_signed(big_endian_to_int(state.stack.pop()))
    mod = unsigned_to_signed(big_endian_to_int(state.stack.pop()))

    if mod == 0:
        result = 0
    else:
        pos_or_neg = -1 if value < 0 else 1
        result = (abs(value) % abs(mod) * pos_or_neg) & UINT_256_MAX

    logger.info('SMOD: %s * |%s| %% |%s| -> %s', pos_or_neg, value, mod, result)
    state.stack.push(
        int_to_big_endian(signed_to_unsigned(result))
    )
    state.consume_gas(COST_LOW)


def mul(message, storage, state):
    """
    Multiplication
    """
    left = big_endian_to_int(state.stack.pop())
    right = big_endian_to_int(state.stack.pop())
    result = (left * right) & UINT_256_MAX
    logger.info('MUL: %s * %s -> %s', left, right, result)
    state.stack.push(
        int_to_big_endian(result)
    )
    state.consume_gas(COST_LOW)


def mulmod(message, storage, state):
    """
    Modulo Multiplication
    """
    left = big_endian_to_int(state.stack.pop())
    right = big_endian_to_int(state.stack.pop())
    mod = big_endian_to_int(state.stack.pop())

    if mod == 0:
        result = 0
    else:
        result = (left * right) % mod
    logger.info('MULMOD: (%s * %s) %% %s -> %s', left, right, mod, result)
    state.stack.push(
        int_to_big_endian(result)
    )
    state.consume_gas(COST_MID)


def div(message, storage, state):
    """
    Division
    """
    numerator = big_endian_to_int(state.stack.pop())
    denominator = big_endian_to_int(state.stack.pop())
    if denominator == 0:
        result = 0
    else:
        result = (numerator // denominator) & UINT_256_MAX
    logger.info('DIV: %s / %s -> %s', numerator, denominator, result)
    state.stack.push(
        int_to_big_endian(result)
    )
    state.consume_gas(COST_LOW)


def sdiv(message, storage, state):
    """
    Signed Division
    """
    numerator = unsigned_to_signed(big_endian_to_int(state.stack.pop()))
    denominator = unsigned_to_signed(big_endian_to_int(state.stack.pop()))

    if denominator == 0:
        pos_or_neg = 1
        result = 0
    else:
        pos_or_neg = -1 if numerator * denominator < 0 else 1
        result = (pos_or_neg * (abs(numerator) // abs(denominator)))
    logger.info('SDIV: %s * |%s| / |%s| -> %s', pos_or_neg, numerator, denominator, result)
    state.stack.push(
        int_to_big_endian(signed_to_unsigned(result))
    )
    state.consume_gas(COST_LOW)


def exp(message, storage, state):
    """
    Exponentiation
    """
    base = big_endian_to_int(state.stack.pop())
    exponent = big_endian_to_int(state.stack.pop())

    bit_size = exponent.bit_length()
    byte_size = ceil8(bit_size) // 8

    if base == 0:
        result = 0
    else:
        result = pow(base, exponent, UINT_256_CEILING)
    logger.info('EXP: %s ** %s -> %s', base, exponent, result)
    state.stack.push(
        int_to_big_endian(result)
    )
    state.consume_gas(COST_EXP)
    state.consume_gas(COST_EXPBYTE * byte_size)
