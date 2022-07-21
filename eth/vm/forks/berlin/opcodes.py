import copy
from typing import (
    Dict,
)

from eth_utils.toolz import (
    merge,
)

from eth import (
    constants,
)
from eth.abc import (
    OpcodeAPI,
)
from eth.vm import (
    mnemonics,
    opcode_values,
)
from eth.vm.forks.byzantium.opcodes import (
    ensure_no_static,
)
from eth.vm.forks.muir_glacier.opcodes import (
    MUIR_GLACIER_OPCODES,
)
from eth.vm.forks.tangerine_whistle.constants import (
    GAS_SELFDESTRUCT_EIP150,
)
from eth.vm.opcode import (
    as_opcode,
)

from . import (
    logic,
)

UPDATED_OPCODES: Dict[int, OpcodeAPI] = {
    opcode_values.BALANCE: as_opcode(
        gas_cost=constants.GAS_NULL,
        logic_fn=logic.balance_eip2929,
        mnemonic=mnemonics.BALANCE,
    ),
    opcode_values.EXTCODESIZE: as_opcode(
        gas_cost=constants.GAS_NULL,
        logic_fn=logic.extcodesize_eip2929,
        mnemonic=mnemonics.EXTCODESIZE,
    ),
    opcode_values.EXTCODECOPY: as_opcode(
        gas_cost=constants.GAS_NULL,
        logic_fn=logic.extcodecopy_eip2929,
        mnemonic=mnemonics.EXTCODECOPY,
    ),
    opcode_values.EXTCODEHASH: as_opcode(
        gas_cost=constants.GAS_NULL,
        logic_fn=logic.extcodehash_eip2929,
        mnemonic=mnemonics.EXTCODEHASH,
    ),
    opcode_values.SLOAD: as_opcode(
        gas_cost=constants.GAS_NULL,
        logic_fn=logic.sload_eip2929,
        mnemonic=mnemonics.SLOAD,
    ),
    opcode_values.SSTORE: as_opcode(
        logic_fn=ensure_no_static(logic.sstore_eip2929),
        mnemonic=mnemonics.SSTORE,
        gas_cost=constants.GAS_NULL,
    ),
    # System opcodes
    opcode_values.CREATE: logic.CreateEIP2929.configure(
        __name__="opcode:CREATE",
        mnemonic=mnemonics.CREATE,
        gas_cost=constants.GAS_CREATE,
    )(),
    opcode_values.CALL: logic.CallEIP2929.configure(
        __name__="opcode:CALL",
        mnemonic=mnemonics.CALL,
        gas_cost=constants.GAS_NULL,
    )(),
    opcode_values.CALLCODE: logic.CallCodeEIP2929.configure(
        __name__="opcode:CALLCODE",
        mnemonic=mnemonics.CALLCODE,
        gas_cost=constants.GAS_NULL,
    )(),
    opcode_values.DELEGATECALL: logic.DelegateCallEIP2929.configure(
        __name__="opcode:DELEGATECALL",
        mnemonic=mnemonics.DELEGATECALL,
        gas_cost=constants.GAS_NULL,
    )(),
    opcode_values.CREATE2: logic.Create2EIP2929.configure(
        __name__="opcode:CREATE2",
        mnemonic=mnemonics.CREATE2,
        gas_cost=constants.GAS_CREATE,
    )(),
    opcode_values.STATICCALL: logic.StaticCallEIP2929.configure(
        __name__="opcode:STATICCALL",
        mnemonic=mnemonics.STATICCALL,
        gas_cost=constants.GAS_NULL,
    )(),
    opcode_values.SELFDESTRUCT: as_opcode(
        logic_fn=ensure_no_static(logic.selfdestruct_eip2929),
        mnemonic=mnemonics.SELFDESTRUCT,
        gas_cost=GAS_SELFDESTRUCT_EIP150,
    ),
}


BERLIN_OPCODES = merge(
    copy.deepcopy(MUIR_GLACIER_OPCODES),
    UPDATED_OPCODES,
)
