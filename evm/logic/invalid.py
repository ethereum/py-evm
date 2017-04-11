from evm.exceptions import InvalidInstruction
from evm.opcode import Opcode


class InvalidOpcode(Opcode):
    mnemonic = "INVALID"
    gas_cost = 0

    def __init__(self, value):
        self.value = value
        super(InvalidOpcode, self).__init__()

    def __call__(self, computation):
        raise InvalidInstruction("Invalid opcode 0x{0:x} @ {1}".format(
            self.value,
            computation.code.pc - 1,
        ))
