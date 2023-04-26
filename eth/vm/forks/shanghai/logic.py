from eth._utils.numeric import (
    ceil32,
)
from eth.vm.forks.berlin.logic import (
    Create2EIP2929,
    CreateEIP2929,
)
from eth.vm.logic.system import (
    CreateOpcodeStackData,
)

from .constants import (
    INITCODE_WORD_COST,
)


class CreateEIP3860(CreateEIP2929):
    def get_gas_cost(self, data: CreateOpcodeStackData) -> int:
        eip2929_gas_cost = super().get_gas_cost(data)
        eip3860_gas_cost = INITCODE_WORD_COST * ceil32(data.memory_length) // 32
        return eip2929_gas_cost + eip3860_gas_cost


class Create2EIP3860(Create2EIP2929):
    def get_gas_cost(self, data: CreateOpcodeStackData) -> int:
        eip2929_gas_cost = super().get_gas_cost(data)
        eip3860_gas_cost = INITCODE_WORD_COST * ceil32(data.memory_length) // 32
        return eip2929_gas_cost + eip3860_gas_cost
