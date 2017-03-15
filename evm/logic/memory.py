import logging

from eth_utils import (
    pad_left,
)

from evm.gas import (
    COST_VERYLOW,
)
from evm.utils.numeric import (
    big_endian_to_int,
)


logger = logging.getLogger('evm.logic.memory')


def mstore(message, storage, state):
    start_position = big_endian_to_int(state.stack.pop())
    value = state.stack.pop()
    padded_value = pad_left(value, 32, b'\x00')

    state.extend_memory(start_position, 32)

    original_value = state.memory.read(start_position, 32)
    state.memory.write(start_position, 32,  padded_value)

    logger.info(
        'MSTORE: (%s:%s) %s -> %s',
        start_position,
        start_position + 32,
        original_value,
        padded_value,
    )
    state.consume_gas(COST_VERYLOW)
