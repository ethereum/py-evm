import logging

from evm.constants import (
    UINT_256_MAX,
)
from evm.gas import (
    COST_VERYLOW,
    COST_MID,
)

from evm.utils.numeric import (
    big_endian_to_int,
    int_to_big_endian,
)


logger = logging.getLogger('evm.logic.arithmetic.add')


def add(message, storage, state):
    left = big_endian_to_int(state.stack.pop())
    right = big_endian_to_int(state.stack.pop())
    result = (left + right) & UINT_256_MAX
    logger.info('ADD: %s + %s -> %s', left, right, result)
    state.stack.push(
        int_to_big_endian(result)
    )
    state.consume_gas(COST_VERYLOW)


def addmod(message, storage, state):
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
