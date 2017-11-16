import copy

from cytoolz import merge

from evm import constants
from evm import opcode_values
from evm import mnemonics

from evm.opcode import as_opcode

from evm.logic import (
    arithmetic,
    system,
    call,
)

from evm.vm.forks.eip150.opcodes import EIP150_OPCODES


UPDATED_OPCODES = {
    opcode_values.EXP: as_opcode(
        logic_fn=arithmetic.exp(gas_per_byte=constants.GAS_EXPBYTE_EIP160),
        mnemonic=mnemonics.EXP,
        gas_cost=constants.GAS_EXP_EIP160,
    ),
    opcode_values.SELFDESTRUCT: as_opcode(
        logic_fn=system.selfdestruct_eip161,
        mnemonic=mnemonics.SELFDESTRUCT,
        gas_cost=constants.GAS_SELFDESTRUCT_EIP150,
    ),
    opcode_values.CALL: call.CallEIP161.configure(
        name='opcode:CALL',
        mnemonic=mnemonics.CALL,
        gas_cost=constants.GAS_CALL_EIP150,
    )(),
}


SPURIOUS_DRAGON_OPCODES = merge(
    copy.deepcopy(EIP150_OPCODES),
    UPDATED_OPCODES,
)
