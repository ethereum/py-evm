from eth.exceptions import (
    InvalidJumpDestination,
    InvalidInstruction,
    OutOfGas,
    Halt,
    InsufficientStack,
)

from eth.vm.computation import BaseComputation
from eth.vm.opcode_values import (
    JUMPDEST,
    BEGINSUB,
)


def stop(computation: BaseComputation) -> None:
    raise Halt('STOP')


def jump(computation: BaseComputation) -> None:
    jump_dest = computation.stack_pop1_int()

    computation.code.program_counter = jump_dest

    next_opcode = computation.code.peek()

    if next_opcode != JUMPDEST:
        raise InvalidJumpDestination("Invalid Jump Destination")

    if not computation.code.is_valid_opcode(jump_dest):
        raise InvalidInstruction("Jump resulted in invalid instruction")


def jumpi(computation: BaseComputation) -> None:
    jump_dest, check_value = computation.stack_pop_ints(2)

    if check_value:
        computation.code.program_counter = jump_dest

        next_opcode = computation.code.peek()

        if next_opcode != JUMPDEST:
            raise InvalidJumpDestination("Invalid Jump Destination")

        if not computation.code.is_valid_opcode(jump_dest):
            raise InvalidInstruction("Jump resulted in invalid instruction")


def jumpdest(computation: BaseComputation) -> None:
    pass


def program_counter(computation: BaseComputation) -> None:
    pc = max(computation.code.program_counter - 1, 0)

    computation.stack_push_int(pc)


def gas(computation: BaseComputation) -> None:
    gas_remaining = computation.get_gas_remaining()

    computation.stack_push_int(gas_remaining)


def beginsub(computation: BaseComputation) -> None:
    raise OutOfGas("Error: at pc={}, op=BEGINSUB: invalid subroutine entry".format(
        computation.code.program_counter)
    )


def jumpsub(computation: BaseComputation) -> None:
    sub_loc = computation.stack_pop1_int()
    code_range_length = len(computation.code)

    if sub_loc >= code_range_length:
        raise InvalidJumpDestination(
            "Error: at pc={}, code_length={}, op=JUMPSUB: invalid jump destination".format(
                computation.code.program_counter,
                code_range_length)
        )

    if computation.code.is_valid_opcode(sub_loc):

        sub_op = computation.code[sub_loc]

        if sub_op == BEGINSUB:
            temp = computation.code.program_counter
            computation.code.program_counter = sub_loc + 1
            computation.rstack_push_int(temp)

        else:
            raise InvalidJumpDestination(
                "Error: at pc={}, code_length={}, op=JUMPSUB: invalid jump destination".format(
                    computation.code.program_counter,
                    code_range_length)
            )


def returnsub(computation: BaseComputation) -> None:
    try:
        ret_loc = computation.rstack_pop1_int()
    except InsufficientStack:
        raise InsufficientStack(
            "Error: at pc={}, op=RETURNSUB: invalid retsub".format(
                computation.code.program_counter)
        )

    computation.code.program_counter = ret_loc
