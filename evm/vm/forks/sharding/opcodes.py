import copy
from cytoolz import (
    merge,
    dissoc,
)

from evm.vm.forks.tangerine_whistle.constants import (
    GAS_CALL_EIP150,
)
from evm.vm import mnemonics
from evm.vm import opcode_values
from evm.vm.logic import (
    call,
)

from evm.vm.forks.byzantium.opcodes import BYZANTIUM_OPCODES


NEW_OPCODES = {

}

REMOVED_OPCODES = [
    opcode_values.CREATE,
    opcode_values.SELFDESTRUCT,
]

REPLACED_OPCODES = {
    opcode_values.CALL: call.CallSharding.configure(
        __name__='opcode:CALL',
        mnemonic=mnemonics.CALL,
        gas_cost=GAS_CALL_EIP150,
    )(),
}


SHARDING_OPCODES = merge(
    dissoc(copy.deepcopy(BYZANTIUM_OPCODES), *REMOVED_OPCODES),
    NEW_OPCODES,
    REPLACED_OPCODES,
)
