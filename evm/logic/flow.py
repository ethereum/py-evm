import logging

from evm.exceptions import (
    InvalidJumpDestination,
)
from evm.opcodes import (
    JUMPDEST,
)

from evm.utils.numeric import (
    big_endian_to_int,
)


logger = logging.getLogger('evm.logic.flow')


def stop(environment):
    logger.info('STOP')


def jump(environment):
    jump_dest = big_endian_to_int(environment.state.stack.pop())

    environment.state.code.pc = jump_dest

    next_opcode = environment.state.code.peek()

    if next_opcode != JUMPDEST:
        raise InvalidJumpDestination("Invalid Jump Destination")

    logger.info('JUMP: %s', jump_dest)


def jumpi(environment):
    jump_dest = big_endian_to_int(environment.state.stack.pop())
    check_value = big_endian_to_int(environment.state.stack.pop())

    if check_value:
        environment.state.code.pc = jump_dest

        next_opcode = environment.state.code.peek()

        if next_opcode != JUMPDEST:
            raise InvalidJumpDestination("Invalid Jump Destination")

    logger.info('JUMP: %s - %s', jump_dest, check_value)


def jumpdest(environment):
    logger.info('JUMPDEST')
