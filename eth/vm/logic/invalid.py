from typing import (
    TYPE_CHECKING,
)

from eth.exceptions import InvalidInstruction
from eth.vm.opcode import Opcode

if TYPE_CHECKING:
    from eth.vm.computation import BaseComputation  # noqa: F401


class InvalidOpcode(Opcode):
    mnemonic = "INVALID"
    gas_cost = 0

    def __init__(self, value: int) -> None:
        self.value = value
        super().__init__()

    def __call__(self, computation: 'BaseComputation') -> None:
        raise InvalidInstruction("Invalid opcode 0x{0:x} @ {1}".format(
            self.value,
            computation.code.pc - 1,
        ))
