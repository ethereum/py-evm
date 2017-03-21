import logging

from eth_utils import (
    pad_right,
)

from evm.utils.numeric import (
    big_endian_to_int,
)


logger = logging.getLogger('evm.logic.context')


def calldataload(environment):
    """
    Load call data into memory.
    """
    start_position = big_endian_to_int(environment.state.stack.pop())

    value = environment.message.data[start_position:start_position + 32]
    padded_value = pad_right(value, 32, b'\x00')
    normalized_value = padded_value.lstrip(b'\x00')

    logger.info(
        'CALLDATALOAD: [%s:%s] -> %s',
        start_position,
        start_position + 32,
        normalized_value,
    )
    environment.state.stack.push(normalized_value)
