from evm.exceptions import InvalidInstruction


def invalid_op(computation, opcode):
    raise InvalidInstruction("Invalid opcode 0x{0:x} @ {1}".format(
        opcode,
        computation.code.pc - 1,
    ))
