from eth.exceptions import InvalidInstruction
from eth.vm.opcode import Opcode


class InvalidOpcode(Opcode):
    mnemonic = "INVALID"
    gas_cost = 0

    def __init__(self, value):
        self.value = value
        super().__init__()

    def __call__(self, computation):
        raise InvalidInstruction("Invalid opcode 0x{0:x} @ {1}".format(
            self.value,
            computation.code.pc - 1,
        ))
