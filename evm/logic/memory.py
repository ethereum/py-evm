import logging

from toolz import (
    partial,
)

from eth_utils import (
    pad_left,
)

from evm.utils.numeric import (
    big_endian_to_int,
)


logger = logging.getLogger('evm.logic.memory')


def mstore_XX(environment, size):
    start_position = big_endian_to_int(environment.state.stack.pop())
    value = environment.state.stack.pop()
    padded_value = pad_left(value, size, b'\x00')
    normalized_value = padded_value[-1 * size:]

    environment.state.extend_memory(start_position, size)

    original_value = environment.state.memory.read(start_position, size)
    environment.state.memory.write(start_position, size,  normalized_value)

    logger.info(
        'MSTORE%s: (%s:%s) %s -> %s',
        '' if size == 32 else size * 8,
        start_position,
        start_position + size,
        original_value,
        normalized_value,
    )


mstore = partial(mstore_XX, size=32)
mstore8 = partial(mstore_XX, size=1)


def mload(environment):
    start_position = big_endian_to_int(environment.state.stack.pop())

    environment.state.extend_memory(start_position, 32)

    value = environment.state.memory.read(start_position, 32)
    environment.state.stack.push(value)

    logger.info(
        'MLOAD: (%s:%s) -> %s',
        start_position,
        start_position + 32,
        value,
    )
