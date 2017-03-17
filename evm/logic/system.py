
import logging

from evm.exceptions import (
    InvalidJumpDestination,
)
from evm.constants import (
    EMPTY_WORD,
)
from evm.gas import (
    COST_ZERO,
    COST_SUICIDE,
)

from evm.utils.numeric import (
    big_endian_to_int,
)


logger = logging.getLogger('evm.logic.flow')


def return_op(message, storage, state):
    start_position_as_bytes = state.stack.pop()
    size_as_bytes = state.stack.pop()

    start_position = big_endian_to_int(start_position_as_bytes)
    size = big_endian_to_int(size_as_bytes)

    state.extend_memory(start_position, size)

    output = state.memory.read(start_position, size)
    state.output = output

    logger.info('RETURN: (%s:%s) -> %s', start_position, start_position + size, output)

    state.consume_gas(COST_ZERO)


def suicide(message, storage, state):
    # TODO
    pass
