import logging

from evm.exceptions import (
    InvalidJumpDestination,
)
from evm.constants import (
    EMPTY_WORD,
)
from evm.gas import (
    COST_ZERO,
    COST_MID,
    COST_HIGH,
    COST_SSET,
    COST_SRESET,
    REFUND_SCLEAR,
    COST_JUMPDEST,
)
from evm.opcodes import (
    JUMPDEST,
)

from evm.utils.numeric import (
    big_endian_to_int,
)


logger = logging.getLogger('evm.logic.flow')


def return_op(message, storage, state):
    start_position_as_bytes = state.stack.pop()
    size_as_bytes = state.stack.pop()

    start_position = big_endian_to_int(start_position_as_bytes)
    size = big_endian_to_int(size_as_bytes)

    state.extend_memory(start_position, size)

    output = state.memory.read(start_position, size)
    state.output = output

    logger.info('RETURN: (%s:%s) -> %s', start_position, start_position + size, output)

    state.consume_gas(COST_ZERO)


def stop(message, storage, state):
    logger.info('STOP')

    state.consume_gas(COST_ZERO)


def jump(message, storage, state):
    jump_dest = big_endian_to_int(state.stack.pop())

    state.pc = jump_dest

    next_opcode = next(state.code)

    if next_opcode != JUMPDEST:
        raise InvalidJumpDestination("Invalid Jump Destination")

    state.pc -= 1

    logger.info('JUMP: %s', jump_dest)

    state.consume_gas(COST_MID)


def jumpi(message, storage, state):
    jump_dest = big_endian_to_int(state.stack.pop())
    check_value = big_endian_to_int(state.stack.pop())

    if check_value:
        state.pc = jump_dest

        next_opcode = next(state.code)

        if next_opcode != JUMPDEST:
            raise InvalidJumpDestination("Invalid Jump Destination")

        state.pc -= 1

    logger.info('JUMP: %s - %s', jump_dest, check_value)

    state.consume_gas(COST_HIGH)


def jumpdest(message, storage, state):
    logger.info('JUMPDEST')

    state.consume_gas(COST_JUMPDEST)
