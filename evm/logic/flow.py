import logging

from evm.exceptions import (
    InvalidJumpDestination,
    InvalidInstruction,
)
from evm.opcodes import (
    JUMPDEST,
)

from evm.utils.numeric import (
    big_endian_to_int,
    int_to_big_endian,
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

    if not environment.state.code.is_valid_opcode(jump_dest):
        raise InvalidInstruction("Jump resulted in invalid instruction")

    logger.info('JUMP: %s', jump_dest)


def jumpi(environment):
    jump_dest = big_endian_to_int(environment.state.stack.pop())
    check_value = big_endian_to_int(environment.state.stack.pop())

    if check_value:
        environment.state.code.pc = jump_dest

        next_opcode = environment.state.code.peek()

        if next_opcode != JUMPDEST:
            raise InvalidJumpDestination("Invalid Jump Destination")

        if not environment.state.code.is_valid_opcode(jump_dest):
            raise InvalidInstruction("Jump resulted in invalid instruction")

    logger.info('JUMP: %s - %s', jump_dest, check_value)


def jumpdest(environment):
    logger.info('JUMPDEST')


def pc(environment):
    pc = max(environment.state.code.pc - 1, 0)
    logger.info('PC: %s', pc)

    environment.state.stack.push(int_to_big_endian(pc))


def gas(environment):
    gas_remaining = environment.state.gas_meter.gas_remaining
    logger.info('GAS: %s', gas_remaining)

    environment.state.stack.push(int_to_big_endian(gas_remaining))
