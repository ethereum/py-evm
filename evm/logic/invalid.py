from evm.exceptions import InvalidInstruction


def invalid_op(environment, opcode):
    raise InvalidInstruction("Invalid opcode 0x{0:x} @ {1}".format(
        opcode,
        environment.state.code.pc,
    ))
