import copy
from cytoolz import (
    merge,
    dissoc,
)

from evm import constants
from evm.vm.forks.tangerine_whistle.constants import (
    GAS_CALL_EIP150,
)
from evm import opcode_values
from evm import mnemonics

from evm.opcode import as_opcode
from evm.logic import (
    call,
    context,
    system,
)

from evm.vm.forks.byzantium.opcodes import BYZANTIUM_OPCODES


NEW_OPCODES = {
    opcode_values.SIGHASH: as_opcode(
        logic_fn=context.sighash,
        mnemonic=mnemonics.SIGHASH,
        gas_cost=constants.GAS_BASE,
    ),
    opcode_values.CREATE2: system.Create2.configure(
        __name__='opcode:CREATE2',
        mnemonic=mnemonics.CREATE2,
        gas_cost=constants.GAS_CREATE2,
    )(),
    opcode_values.PAYGAS: as_opcode(
        logic_fn=system.paygas,
        mnemonic=mnemonics.PAYGAS,
        gas_cost=constants.GAS_VERYLOW,
    ),
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
    opcode_values.GASPRICE: as_opcode(
        logic_fn=context.PAYGAS_gasprice,
        mnemonic=mnemonics.GASPRICE,
        gas_cost=constants.GAS_BASE,
    ),
}


SHARDING_OPCODES = merge(
    dissoc(copy.deepcopy(BYZANTIUM_OPCODES), *REMOVED_OPCODES),
    NEW_OPCODES,
    REPLACED_OPCODES,
)
