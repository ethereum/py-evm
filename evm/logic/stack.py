import logging

from toolz import (
    partial,
)

from eth_utils import (
    pad_left,
)

from evm.gas import (
    COST_BASE,
)
from evm.utils.numeric import (
    big_endian_to_int,
)


logger = logging.getLogger('evm.logic.memory')


def pop(message, storage, state):
    removed_value = state.stack.pop()

    logger.info('POP: %s', removed_value)
    state.consume_gas(COST_BASE)
