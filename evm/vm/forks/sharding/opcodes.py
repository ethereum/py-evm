import copy
from cytoolz import merge

from evm import opcode_values
from evm import mnemonics

from evm.opcode import as_opcode
from evm.logic import (
    context,
)

from evm.vm.forks.byzantium import BYZANTIUM_OPCODES


NEW_OPCODES = {
    opcode_values.SIGHASH: as_opcode(
        logic_fn=context.sighash,
        mnemonic=mnemonics.SIGHASH,
        gas_cost=0,
    ),
}


SHARDING_OPCODES = merge(
    copy.deepcopy(BYZANTIUM_OPCODES),
    NEW_OPCODES
)
