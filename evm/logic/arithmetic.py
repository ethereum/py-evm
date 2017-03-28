import logging
import functools

from toolz import (
    map,
)

from evm import constants

from evm.utils.numeric import (
    unsigned_to_signed,
    signed_to_unsigned,
    ceil8,
)


logger = logging.getLogger('evm.logic.arithmetic')



def add(computation):
    """
    Addition
    """
    left, right = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    result = (left + right) & constants.UINT_256_MAX

    logger.info('ADD: %s + %s -> %s', left, right, result)
    computation.stack.push(result)


def addmod(computation):
    """
    Modulo Addition
    """
    left, right, mod = computation.stack.pop(num_items=3, type_hint=constants.UINT256)

    if mod == 0:
        result = 0
    else:
        result = (left + right) % mod
    logger.info('ADDMOD: (%s + %s) %% %s -> %s', left, right, mod, result)
    computation.stack.push(result)


def sub(computation):
    """
    Subtraction
    """
    left, right = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    result = (left - right) & constants.UINT_256_MAX

    logger.info('SUB: %s - %s -> %s', left, right, result)
    computation.stack.push(result)


def mod(computation):
    """
    Modulo
    """
    value, mod = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    if mod == 0:
        result = 0
    else:
        result = value % mod

    logger.info('MOD: %s %% %s -> %s', value, mod, result)
    computation.stack.push(result)


def smod(computation):
    """
    Signed Modulo
    """
    value, mod = map(
        unsigned_to_signed,
        computation.stack.pop(num_items=2, type_hint=constants.UINT256),
    )

    pos_or_neg = -1 if value < 0 else 1

    if mod == 0:
        result = 0
    else:
        result = (abs(value) % abs(mod) * pos_or_neg) & constants.UINT_256_MAX

    logger.info('SMOD: %s * |%s| %% |%s| -> %s', pos_or_neg, value, mod, result)
    computation.stack.push(signed_to_unsigned(result))


def mul(computation):
    """
    Multiplication
    """
    left, right = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    result = (left * right) & constants.UINT_256_MAX

    logger.info('MUL: %s * %s -> %s', left, right, result)
    computation.stack.push(result)


def mulmod(computation):
    """
    Modulo Multiplication
    """
    left, right, mod = computation.stack.pop(num_items=3, type_hint=constants.UINT256)

    if mod == 0:
        result = 0
    else:
        result = (left * right) % mod
    logger.info('MULMOD: (%s * %s) %% %s -> %s', left, right, mod, result)
    computation.stack.push(result)


def div(computation):
    """
    Division
    """
    numerator, denominator = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    if denominator == 0:
        result = 0
    else:
        result = (numerator // denominator) & constants.UINT_256_MAX

    logger.info('DIV: %s / %s -> %s', numerator, denominator, result)

    computation.stack.push(result)


def sdiv(computation):
    """
    Signed Division
    """
    numerator, denominator = map(
        unsigned_to_signed,
        computation.stack.pop(num_items=2, type_hint=constants.UINT256),
    )

    pos_or_neg = -1 if numerator * denominator < 0 else 1

    if denominator == 0:
        result = 0
    else:
        result = (pos_or_neg * (abs(numerator) // abs(denominator)))

    logger.info('SDIV: %s * |%s| / |%s| -> %s', pos_or_neg, numerator, denominator, result)

    computation.stack.push(signed_to_unsigned(result))


def exp(computation):
    """
    Exponentiation
    """
    base, exponent = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    bit_size = exponent.bit_length()
    byte_size = ceil8(bit_size) // 8

    if base == 0:
        result = 0
    else:
        result = pow(base, exponent, constants.UINT_256_CEILING)

    logger.info('EXP: %s ** %s -> %s', base, exponent, result)

    computation.gas_meter.consume_gas(
        constants.GAS_EXPBYTE * byte_size,
        reason="EXP: exponent bytes",
    )
    if computation.gas_meter.is_out_of_gas:
        raise OutOfGas("Ran out of gas during exponentiation")

    computation.stack.push(result)


def signextend(computation):
    """
    Signed Extend
    """
    bits, value = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    if bits <= 31:
        testbit = bits * 8 + 7
        sign_bit = (1 << testbit)
        if value & sign_bit:
            result = value | (constants.UINT_256_CEILING - sign_bit)
        else:
            result = value & (sign_bit - 1)
    else:
        result = value

    logger.info('SIGNEXTEND: %s by %s bits -> %s', value, bits, result)
    computation.stack.push(result)
