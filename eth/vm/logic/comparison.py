from eth import (
    constants,
)
from eth._utils.numeric import (
    signed_to_unsigned,
    unsigned_to_signed,
)
from eth.abc import (
    ComputationAPI,
)


def lt(computation: ComputationAPI) -> None:
    """
    Lesser Comparison
    """
    left, right = computation.stack_pop_ints(2)

    if left < right:
        result = 1
    else:
        result = 0

    computation.stack_push_int(result)


def gt(computation: ComputationAPI) -> None:
    """
    Greater Comparison
    """
    left, right = computation.stack_pop_ints(2)

    if left > right:
        result = 1
    else:
        result = 0

    computation.stack_push_int(result)


def slt(computation: ComputationAPI) -> None:
    """
    Signed Lesser Comparison
    """
    left, right = map(
        unsigned_to_signed,
        computation.stack_pop_ints(2),
    )

    if left < right:
        result = 1
    else:
        result = 0

    computation.stack_push_int(signed_to_unsigned(result))


def sgt(computation: ComputationAPI) -> None:
    """
    Signed Greater Comparison
    """
    left, right = map(
        unsigned_to_signed,
        computation.stack_pop_ints(2),
    )

    if left > right:
        result = 1
    else:
        result = 0

    computation.stack_push_int(signed_to_unsigned(result))


def eq(computation: ComputationAPI) -> None:
    """
    Equality
    """
    left, right = computation.stack_pop_ints(2)

    if left == right:
        result = 1
    else:
        result = 0

    computation.stack_push_int(result)


def iszero(computation: ComputationAPI) -> None:
    """
    Not
    """
    value = computation.stack_pop1_int()

    if value == 0:
        result = 1
    else:
        result = 0

    computation.stack_push_int(result)


def and_op(computation: ComputationAPI) -> None:
    """
    Bitwise And
    """
    left, right = computation.stack_pop_ints(2)

    result = left & right

    computation.stack_push_int(result)


def or_op(computation: ComputationAPI) -> None:
    """
    Bitwise Or
    """
    left, right = computation.stack_pop_ints(2)

    result = left | right

    computation.stack_push_int(result)


def xor(computation: ComputationAPI) -> None:
    """
    Bitwise XOr
    """
    left, right = computation.stack_pop_ints(2)

    result = left ^ right

    computation.stack_push_int(result)


def not_op(computation: ComputationAPI) -> None:
    """
    Not
    """
    value = computation.stack_pop1_int()

    result = constants.UINT_256_MAX - value

    computation.stack_push_int(result)


def byte_op(computation: ComputationAPI) -> None:
    """
    Bitwise And
    """
    position, value = computation.stack_pop_ints(2)

    if position >= 32:
        result = 0
    else:
        result = (value // pow(256, 31 - position)) % 256

    computation.stack_push_int(result)
