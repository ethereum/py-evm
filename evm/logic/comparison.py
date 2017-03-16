import logging

from evm.constants import (
    UINT_256_MAX,
)
from evm.gas import (
    COST_VERYLOW,
)

from evm.utils.numeric import (
    big_endian_to_int,
    int_to_big_endian,
    signed_to_unsigned,
    unsigned_to_signed,
)


logger = logging.getLogger('evm.logic.comparison')


def lt(message, storage, state):
    """
    Lesser Comparison
    """
    left = big_endian_to_int(state.stack.pop())
    right = big_endian_to_int(state.stack.pop())

    if left < right:
        result = 1
    else:
        result = 0

    logger.info('LT: %s < %s -> %s', left, right, result)
    state.stack.push(
        int_to_big_endian(result)
    )
    state.consume_gas(COST_VERYLOW)


def gt(message, storage, state):
    """
    Greater Comparison
    """
    left = big_endian_to_int(state.stack.pop())
    right = big_endian_to_int(state.stack.pop())

    if left > right:
        result = 1
    else:
        result = 0

    logger.info('SGT: %s > %s -> %s', left, right, result)
    state.stack.push(
        int_to_big_endian(result)
    )
    state.consume_gas(COST_VERYLOW)


def slt(message, storage, state):
    """
    Signed Lesser Comparison
    """
    left = unsigned_to_signed(big_endian_to_int(state.stack.pop()))
    right = unsigned_to_signed(big_endian_to_int(state.stack.pop()))

    if left < right:
        result = 1
    else:
        result = 0

    logger.info('SLT: %s < %s -> %s', left, right, result)
    state.stack.push(
        int_to_big_endian(signed_to_unsigned(result))
    )
    state.consume_gas(COST_VERYLOW)


def sgt(message, storage, state):
    """
    Signed Greater Comparison
    """
    left = unsigned_to_signed(big_endian_to_int(state.stack.pop()))
    right = unsigned_to_signed(big_endian_to_int(state.stack.pop()))

    if left > right:
        result = 1
    else:
        result = 0

    logger.info('SGT: %s > %s -> %s', left, right, result)
    state.stack.push(
        int_to_big_endian(signed_to_unsigned(result))
    )
    state.consume_gas(COST_VERYLOW)


def eq(message, storage, state):
    """
    Equality
    """
    left = big_endian_to_int(state.stack.pop())
    right = big_endian_to_int(state.stack.pop())

    if left == right:
        result = 1
    else:
        result = 0

    logger.info('EQ: %s == %s -> %s', left, right, result)
    state.stack.push(
        int_to_big_endian(result)
    )
    state.consume_gas(COST_VERYLOW)


def iszero(message, storage, state):
    """
    Not
    """
    value = big_endian_to_int(state.stack.pop())

    if value == 0:
        result = 1
    else:
        result = 0

    logger.info('ISZERO: %s -> %s', value, result)
    state.stack.push(int_to_big_endian(result))

    state.consume_gas(COST_VERYLOW)


def and_op(message, storage, state):
    """
    Bitwise And
    """
    left = big_endian_to_int(state.stack.pop())
    right = big_endian_to_int(state.stack.pop())

    result = left & right

    logger.info('AND: %s & %s -> %s', left, right, result)
    state.stack.push(
        int_to_big_endian(result)
    )
    state.consume_gas(COST_VERYLOW)




def or_op(message, storage, state):
    """
    Bitwise Or
    """
    left = big_endian_to_int(state.stack.pop())
    right = big_endian_to_int(state.stack.pop())

    result = left | right

    logger.info('OR: %s | %s -> %s', left, right, result)
    state.stack.push(
        int_to_big_endian(result)
    )
    state.consume_gas(COST_VERYLOW)


def xor(message, storage, state):
    """
    Bitwise XOr
    """
    left = big_endian_to_int(state.stack.pop())
    right = big_endian_to_int(state.stack.pop())

    result = left ^ right

    logger.info('XOR: %s ^ %s -> %s', left, right, result)
    state.stack.push(
        int_to_big_endian(result)
    )
    state.consume_gas(COST_VERYLOW)


def not_op(message, storage, state):
    """
    Not
    """
    value_as_bytes = state.stack.pop()
    value = big_endian_to_int(value_as_bytes)

    result = UINT_256_MAX - value
    result_as_bytes = int_to_big_endian(result)

    logger.info('NOT: %s -> %s', value, result)
    state.stack.push(result_as_bytes)

    state.consume_gas(COST_VERYLOW)


def byte_op(message, storage, state):
    """
    Bitwise And
    """
    position = big_endian_to_int(state.stack.pop())
    value = big_endian_to_int(state.stack.pop())

    if position >= 32:
        result = 0
    else:
        result = (value // pow(256, 31 - position)) % 256

    logger.info('BYTE: %s[%s] -> %s', value, position, result)
    state.stack.push(
        int_to_big_endian(result)
    )
    state.consume_gas(COST_VERYLOW)
