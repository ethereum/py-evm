import copy

from cytoolz import merge

from evm.vm.forks.tangerine_whistle.constants import (
    GAS_SELFDESTRUCT_EIP150,
    GAS_CALL_EIP150
)
from evm import opcode_values
from evm import mnemonics

from evm.opcode import as_opcode

from evm.logic import (
    arithmetic,
    system,
    call,
)

from evm.vm.forks.tangerine_whistle.opcodes import TANGERINE_WHISTLE_OPCODES

from .constants import (
    GAS_EXP_EIP160,
    GAS_EXPBYTE_EIP160
)


UPDATED_OPCODES = {
    opcode_values.EXP: as_opcode(
        logic_fn=arithmetic.exp(gas_per_byte=GAS_EXPBYTE_EIP160),
        mnemonic=mnemonics.EXP,
        gas_cost=GAS_EXP_EIP160,
    ),
    opcode_values.SELFDESTRUCT: as_opcode(
        logic_fn=system.selfdestruct_eip161,
        mnemonic=mnemonics.SELFDESTRUCT,
        gas_cost=GAS_SELFDESTRUCT_EIP150,
    ),
    opcode_values.CALL: call.CallEIP161.configure(
        __name__='opcode:CALL',
        mnemonic=mnemonics.CALL,
        gas_cost=GAS_CALL_EIP150,
    )(),
}


SPURIOUS_DRAGON_OPCODES = merge(
    copy.deepcopy(TANGERINE_WHISTLE_OPCODES),
    UPDATED_OPCODES,
)
