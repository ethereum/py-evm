from evm import constants

from evm.utils.numeric import (
    signed_to_unsigned,
    unsigned_to_signed,
)


def lt(computation):
    """
    Lesser Comparison
    """
    left, right = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    if left < right:
        result = 1
    else:
        result = 0

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

    computation.stack.push(result)


def and_op(computation):
    """
    Bitwise And
    """
    left, right = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    result = left & right

    computation.stack.push(result)


def or_op(computation):
    """
    Bitwise Or
    """
    left, right = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    result = left | right

    computation.stack.push(result)


def xor(computation):
    """
    Bitwise XOr
    """
    left, right = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    result = left ^ right

    computation.stack.push(result)


def not_op(computation):
    """
    Not
    """
    value = computation.stack.pop(type_hint=constants.UINT256)

    result = constants.UINT_256_MAX - value

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

    computation.stack.push(result)
