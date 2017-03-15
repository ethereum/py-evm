import logging

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
