import logging

from evm import constants

from evm.utils.numeric import (
    big_endian_to_int,
    int_to_big_endian,
    signed_to_unsigned,
    unsigned_to_signed,
)


logger = logging.getLogger('evm.logic.comparison')


def lt(computation):
    """
    Lesser Comparison
    """
    left = big_endian_to_int(computation.stack.pop())
    right = big_endian_to_int(computation.stack.pop())

    if left < right:
        result = 1
    else:
        result = 0

    logger.info('LT: %s < %s -> %s', left, right, result)
    computation.stack.push(
        int_to_big_endian(result)
    )


def gt(computation):
    """
    Greater Comparison
    """
    left = big_endian_to_int(computation.stack.pop())
    right = big_endian_to_int(computation.stack.pop())

    if left > right:
        result = 1
    else:
        result = 0

    logger.info('SGT: %s > %s -> %s', left, right, result)
    computation.stack.push(
        int_to_big_endian(result)
    )


def slt(computation):
    """
    Signed Lesser Comparison
    """
    left = unsigned_to_signed(big_endian_to_int(computation.stack.pop()))
    right = unsigned_to_signed(big_endian_to_int(computation.stack.pop()))

    if left < right:
        result = 1
    else:
        result = 0

    logger.info('SLT: %s < %s -> %s', left, right, result)
    computation.stack.push(
        int_to_big_endian(signed_to_unsigned(result))
    )


def sgt(computation):
    """
    Signed Greater Comparison
    """
    left = unsigned_to_signed(big_endian_to_int(computation.stack.pop()))
    right = unsigned_to_signed(big_endian_to_int(computation.stack.pop()))

    if left > right:
        result = 1
    else:
        result = 0

    logger.info('SGT: %s > %s -> %s', left, right, result)
    computation.stack.push(
        int_to_big_endian(signed_to_unsigned(result))
    )


def eq(computation):
    """
    Equality
    """
    left = big_endian_to_int(computation.stack.pop())
    right = big_endian_to_int(computation.stack.pop())

    if left == right:
        result = 1
    else:
        result = 0

    logger.info('EQ: %s == %s -> %s', left, right, result)
    computation.stack.push(
        int_to_big_endian(result)
    )


def iszero(computation):
    """
    Not
    """
    value = big_endian_to_int(computation.stack.pop())

    if value == 0:
        result = 1
    else:
        result = 0

    logger.info('ISZERO: %s -> %s', value, result)
    computation.stack.push(int_to_big_endian(result))



def and_op(computation):
    """
    Bitwise And
    """
    left = big_endian_to_int(computation.stack.pop())
    right = big_endian_to_int(computation.stack.pop())

    result = left & right

    logger.info('AND: %s & %s -> %s', left, right, result)
    computation.stack.push(
        int_to_big_endian(result)
    )




def or_op(computation):
    """
    Bitwise Or
    """
    left = big_endian_to_int(computation.stack.pop())
    right = big_endian_to_int(computation.stack.pop())

    result = left | right

    logger.info('OR: %s | %s -> %s', left, right, result)
    computation.stack.push(
        int_to_big_endian(result)
    )


def xor(computation):
    """
    Bitwise XOr
    """
    left = big_endian_to_int(computation.stack.pop())
    right = big_endian_to_int(computation.stack.pop())

    result = left ^ right

    logger.info('XOR: %s ^ %s -> %s', left, right, result)
    computation.stack.push(
        int_to_big_endian(result)
    )


def not_op(computation):
    """
    Not
    """
    value_as_bytes = computation.stack.pop()
    value = big_endian_to_int(value_as_bytes)

    result = constants.UINT_256_MAX - value
    result_as_bytes = int_to_big_endian(result)

    logger.info('NOT: %s -> %s', value, result)
    computation.stack.push(result_as_bytes)



def byte_op(computation):
    """
    Bitwise And
    """
    position = big_endian_to_int(computation.stack.pop())
    value = big_endian_to_int(computation.stack.pop())

    if position >= 32:
        result = 0
    else:
        result = (value // pow(256, 31 - position)) % 256

    logger.info('BYTE: %s[%s] -> %s', value, position, result)
    computation.stack.push(
        int_to_big_endian(result)
    )
