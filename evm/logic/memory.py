import logging

from toolz import (
    partial,
)

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


def mstore_XX(message, storage, state, size):
    start_position = big_endian_to_int(state.stack.pop())
    value = state.stack.pop()
    padded_value = pad_left(value, size, b'\x00')
    normalized_value = padded_value[-1 * size:]

    state.extend_memory(start_position, size)

    original_value = state.memory.read(start_position, size)
    state.memory.write(start_position, size,  normalized_value)

    logger.info(
        'MSTORE%s: (%s:%s) %s -> %s',
        '' if size == 32 else size * 8,
        start_position,
        start_position + size,
        original_value,
        normalized_value,
    )
    state.consume_gas(COST_VERYLOW)


mstore = partial(mstore_XX, size=32)
mstore8 = partial(mstore_XX, size=1)


def mload(message, storage, state):
    start_position = big_endian_to_int(state.stack.pop())

    state.extend_memory(start_position, 32)

    value = state.memory.read(start_position, 32)
    state.stack.push(value)

    logger.info(
        'MLOAD: (%s:%s) -> %s',
        start_position,
        start_position + 32,
        value,
    )
    state.consume_gas(COST_VERYLOW)
