import logging

from toolz import (
    map,
)

from evm import constants

from evm.utils.numeric import (
    signed_to_unsigned,
    unsigned_to_signed,
)


logger = logging.getLogger('evm.logic.comparison')


def lt(computation):
    """
    Lesser Comparison
    """
    left, right = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    if left < right:
        result = 1
    else:
        result = 0

    logger.info('LT: %s < %s -> %s', left, right, result)
    computation.stack.push(result)


def gt(computation):
    """
    Greater Comparison
    """
    left, right = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    if left > right:
        result = 1
    else:
        result = 0

    logger.info('SGT: %s > %s -> %s', left, right, result)
    computation.stack.push(result)


def slt(computation):
    """
    Signed Lesser Comparison
    """
    left, right = map(
        unsigned_to_signed,
        computation.stack.pop(num_items=2, type_hint=constants.UINT256),
    )

    if left < right:
        result = 1
    else:
        result = 0

    logger.info('SLT: %s < %s -> %s', left, right, result)
    computation.stack.push(signed_to_unsigned(result))


def sgt(computation):
    """
    Signed Greater Comparison
    """
    left, right = map(
        unsigned_to_signed,
        computation.stack.pop(num_items=2, type_hint=constants.UINT256),
    )

    if left > right:
        result = 1
    else:
        result = 0

    logger.info('SGT: %s > %s -> %s', left, right, result)
    computation.stack.push(signed_to_unsigned(result))


def eq(computation):
    """
    Equality
    """
    left, right = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    if left == right:
        result = 1
    else:
        result = 0

    logger.info('EQ: %s == %s -> %s', left, right, result)
    computation.stack.push(result)


def iszero(computation):
    """
    Not
    """
    value = computation.stack.pop(type_hint=constants.UINT256)

    if value == 0:
        result = 1
    else:
        result = 0

    logger.info('ISZERO: %s -> %s', value, result)
    computation.stack.push(result)



def and_op(computation):
    """
    Bitwise And
    """
    left, right = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    result = left & right

    logger.info('AND: %s & %s -> %s', left, right, result)
    computation.stack.push(result)




def or_op(computation):
    """
    Bitwise Or
    """
    left, right = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    result = left | right

    logger.info('OR: %s | %s -> %s', left, right, result)
    computation.stack.push(result)


def xor(computation):
    """
    Bitwise XOr
    """
    left, right = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    result = left ^ right

    logger.info('XOR: %s ^ %s -> %s', left, right, result)
    computation.stack.push(result)


def not_op(computation):
    """
    Not
    """
    value = computation.stack.pop(type_hint=constants.UINT256)

    result = constants.UINT_256_MAX - value

    logger.info('NOT: %s -> %s', value, result)
    computation.stack.push(result)


def byte_op(computation):
    """
    Bitwise And
    """
    position, value = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    if position >= 32:
        result = 0
    else:
        result = (value // pow(256, 31 - position)) % 256

    logger.info('BYTE: %s[%s] -> %s', value, position, result)
    computation.stack.push(result)
