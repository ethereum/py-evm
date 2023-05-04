from eth.abc import (
    ComputationAPI,
)
from eth.exceptions import (
    Halt,
    InvalidInstruction,
    InvalidJumpDestination,
)
from eth.vm.opcode_values import (
    JUMPDEST,
)


def stop(computation: ComputationAPI) -> None:
    raise Halt("STOP")


def jump(computation: ComputationAPI) -> None:
    jump_dest = computation.stack_pop1_int()

    computation.code.program_counter = jump_dest

    next_opcode = computation.code.peek()

    if next_opcode != JUMPDEST:
        raise InvalidJumpDestination("Invalid Jump Destination")

    if not computation.code.is_valid_opcode(jump_dest):
        raise InvalidInstruction("Jump resulted in invalid instruction")


def jumpi(computation: ComputationAPI) -> None:
    jump_dest, check_value = computation.stack_pop_ints(2)

    if check_value:
        computation.code.program_counter = jump_dest

        next_opcode = computation.code.peek()

        if next_opcode != JUMPDEST:
            raise InvalidJumpDestination("Invalid Jump Destination")

        if not computation.code.is_valid_opcode(jump_dest):
            raise InvalidInstruction("Jump resulted in invalid instruction")


def jumpdest(computation: ComputationAPI) -> None:
    pass


def program_counter(computation: ComputationAPI) -> None:
    pc = max(computation.code.program_counter - 1, 0)

    computation.stack_push_int(pc)


def gas(computation: ComputationAPI) -> None:
    gas_remaining = computation.get_gas_remaining()

    computation.stack_push_int(gas_remaining)
