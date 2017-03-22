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


def stop(computation):
    logger.info('STOP')


def jump(computation):
    jump_dest = big_endian_to_int(computation.stack.pop())

    computation.code.pc = jump_dest

    next_opcode = computation.code.peek()

    if next_opcode != JUMPDEST:
        raise InvalidJumpDestination("Invalid Jump Destination")

    if not computation.code.is_valid_opcode(jump_dest):
        raise InvalidInstruction("Jump resulted in invalid instruction")

    logger.info('JUMP: %s', jump_dest)


def jumpi(computation):
    jump_dest = big_endian_to_int(computation.stack.pop())
    check_value = big_endian_to_int(computation.stack.pop())

    if check_value:
        computation.code.pc = jump_dest

        next_opcode = computation.code.peek()

        if next_opcode != JUMPDEST:
            raise InvalidJumpDestination("Invalid Jump Destination")

        if not computation.code.is_valid_opcode(jump_dest):
            raise InvalidInstruction("Jump resulted in invalid instruction")

    logger.info('JUMP: %s - %s', jump_dest, check_value)


def jumpdest(computation):
    logger.info('JUMPDEST')


def pc(computation):
    pc = max(computation.code.pc - 1, 0)
    logger.info('PC: %s', pc)

    computation.stack.push(int_to_big_endian(pc))


def gas(computation):
    gas_remaining = computation.gas_meter.gas_remaining
    logger.info('GAS: %s', gas_remaining)

    computation.stack.push(int_to_big_endian(gas_remaining))
