import copy
from cytoolz import merge

from evm import constants
from evm import opcode_values
from evm import mnemonics

from evm.opcode import as_opcode
from evm.logic import (
    context,
    system,
)

from evm.vm.forks.byzantium.opcodes import BYZANTIUM_OPCODES


NEW_OPCODES = {
    opcode_values.SIGHASH: as_opcode(
        logic_fn=context.sighash,
        mnemonic=mnemonics.SIGHASH,
        gas_cost=0,
    ),
    opcode_values.CREATE2: system.Create2.configure(
        name='opcode:CREATE2',
        mnemonic=mnemonics.CREATE2,
        gas_cost=constants.GAS_CREATE2,
    )(),
}


SHARDING_OPCODES = merge(
    copy.deepcopy(BYZANTIUM_OPCODES),
    NEW_OPCODES
)
