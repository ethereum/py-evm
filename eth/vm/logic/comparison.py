from eth import constants

from eth._utils.numeric import (
    signed_to_unsigned,
    unsigned_to_signed,
)

from eth.vm.computation import BaseComputation


def lt(computation: BaseComputation) -> None:
    """
    Lesser Comparison
    """
    left, right = computation.stack_pop(num_items=2, type_hint=constants.UINT256)

    if left < right:
        result = 1
    else:
        result = 0

    computation.stack_push(result)


def gt(computation: BaseComputation) -> None:
    """
    Greater Comparison
    """
    left, right = computation.stack_pop(num_items=2, type_hint=constants.UINT256)

    if left > right:
        result = 1
    else:
        result = 0

    computation.stack_push(result)


def slt(computation: BaseComputation) -> None:
    """
    Signed Lesser Comparison
    """
    left, right = map(
        unsigned_to_signed,
        computation.stack_pop(num_items=2, type_hint=constants.UINT256),
    )

    if left < right:
        result = 1
    else:
        result = 0

    computation.stack_push(signed_to_unsigned(result))


def sgt(computation: BaseComputation) -> None:
    """
    Signed Greater Comparison
    """
    left, right = map(
        unsigned_to_signed,
        computation.stack_pop(num_items=2, type_hint=constants.UINT256),
    )

    if left > right:
        result = 1
    else:
        result = 0

    computation.stack_push(signed_to_unsigned(result))


def eq(computation: BaseComputation) -> None:
    """
    Equality
    """
    left, right = computation.stack_pop(num_items=2, type_hint=constants.UINT256)

    if left == right:
        result = 1
    else:
        result = 0

    computation.stack_push(result)


def iszero(computation: BaseComputation) -> None:
    """
    Not
    """
    value = computation.stack_pop(type_hint=constants.UINT256)

    if value == 0:
        result = 1
    else:
        result = 0

    computation.stack_push(result)


def and_op(computation: BaseComputation) -> None:
    """
    Bitwise And
    """
    left, right = computation.stack_pop(num_items=2, type_hint=constants.UINT256)

    result = left & right

    computation.stack_push(result)


def or_op(computation: BaseComputation) -> None:
    """
    Bitwise Or
    """
    left, right = computation.stack_pop(num_items=2, type_hint=constants.UINT256)

    result = left | right

    computation.stack_push(result)


def xor(computation: BaseComputation) -> None:
    """
    Bitwise XOr
    """
    left, right = computation.stack_pop(num_items=2, type_hint=constants.UINT256)

    result = left ^ right

    computation.stack_push(result)


def not_op(computation: BaseComputation) -> None:
    """
    Not
    """
    value = computation.stack_pop(type_hint=constants.UINT256)

    result = constants.UINT_256_MAX - value

    computation.stack_push(result)


def byte_op(computation: BaseComputation) -> None:
    """
    Bitwise And
    """
    position, value = computation.stack_pop(num_items=2, type_hint=constants.UINT256)

    if position >= 32:
        result = 0
    else:
        result = (value // pow(256, 31 - position)) % 256

    computation.stack_push(result)
