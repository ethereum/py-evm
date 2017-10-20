from evm import constants
from evm.exceptions import (
    InvalidJumpDestination,
    InvalidInstruction,
    Halt,
)
from evm.opcode_values import (
    JUMPDEST,
)


def stop(computation):
    raise Halt('STOP')


def jump(computation):
    jump_dest = computation.stack.pop(type_hint=constants.UINT256)

    computation.code.pc = jump_dest

    next_opcode = computation.code.peek()

    if next_opcode != JUMPDEST:
        raise InvalidJumpDestination("Invalid Jump Destination")

    if not computation.code.is_valid_opcode(jump_dest):
        raise InvalidInstruction("Jump resulted in invalid instruction")


def jumpi(computation):
    jump_dest, check_value = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    if check_value:
        computation.code.pc = jump_dest

        next_opcode = computation.code.peek()

        if next_opcode != JUMPDEST:
            raise InvalidJumpDestination("Invalid Jump Destination")

        if not computation.code.is_valid_opcode(jump_dest):
            raise InvalidInstruction("Jump resulted in invalid instruction")


def jumpdest(computation):
    pass


def pc(computation):
    pc = max(computation.code.pc - 1, 0)

    computation.stack.push(pc)


def gas(computation):
    gas_remaining = computation.gas_meter.gas_remaining

    computation.stack.push(gas_remaining)
