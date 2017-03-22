import logging

from toolz import (
    partial,
)

from eth_utils import (
    pad_left,
)

from evm.utils.numeric import (
    big_endian_to_int,
    int_to_big_endian,
)


logger = logging.getLogger('evm.logic.memory')


def mstore_XX(computation, size):
    start_position = big_endian_to_int(computation.stack.pop())
    value = computation.stack.pop()
    padded_value = pad_left(value, size, b'\x00')
    normalized_value = padded_value[-1 * size:]

    computation.extend_memory(start_position, size)

    original_value = computation.memory.read(start_position, size)
    computation.memory.write(start_position, size,  normalized_value)

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


def mload(computation):
    start_position = big_endian_to_int(computation.stack.pop())

    computation.extend_memory(start_position, 32)

    value = computation.memory.read(start_position, 32)
    computation.stack.push(value)

    logger.info(
        'MLOAD: (%s:%s) -> %s',
        start_position,
        start_position + 32,
        value,
    )


def msize(computation):
    logger.info('MSIZE: %s', len(computation.memory))

    computation.stack.push(int_to_big_endian(len(computation.memory)))
