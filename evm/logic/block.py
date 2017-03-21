import logging

from evm.utils.numeric import (
    int_to_big_endian,
)


logger = logging.getLogger('evm.logic.block')


def number(environment):
    logger.info('NUMBER: %s', environment.chain_environment.block_number)
    environment.state.stack.push(int_to_big_endian(environment.chain_environment.block_number))
