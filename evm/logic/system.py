import logging

from evm import constants

from evm.utils.numeric import (
    big_endian_to_int,
    int_to_big_endian,
)


logger = logging.getLogger('evm.logic.system')


def return_op(environment):
    start_position_as_bytes = environment.state.stack.pop()
    size_as_bytes = environment.state.stack.pop()

    start_position = big_endian_to_int(start_position_as_bytes)
    size = big_endian_to_int(size_as_bytes)

    environment.state.extend_memory(start_position, size)

    output = environment.state.memory.read(start_position, size)
    environment.state.output = output

    logger.info('RETURN: (%s:%s) -> %s', start_position, start_position + size, output)


def suicide(environment):
    beneficiary = int_to_big_endian(
        big_endian_to_int(environment.state.stack.pop()) % constants.UINT_160_CEILING
    )
    environment.register_account_for_deletion(beneficiary)
    logger.info('SUICIDE: %s -> %s', environment.message.account, beneficiary)
