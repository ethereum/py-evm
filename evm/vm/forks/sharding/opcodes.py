import copy
from cytoolz import (
    merge,
    dissoc,
)

from evm.vm import opcode_values


from evm.vm.forks.byzantium.opcodes import BYZANTIUM_OPCODES


NEW_OPCODES = {

}

REMOVED_OPCODES = [
    opcode_values.CREATE,
    opcode_values.SELFDESTRUCT,
]

REPLACED_OPCODES = {

}


SHARDING_OPCODES = merge(
    dissoc(copy.deepcopy(BYZANTIUM_OPCODES), *REMOVED_OPCODES),
    NEW_OPCODES,
    REPLACED_OPCODES,
)
