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
)


logger = logging.getLogger('evm.logic.comparison')


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
