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
from eth.vm.forks.cancun.opcodes import (
    CANCUN_OPCODES,
)
from eth.vm.opcode import (
    as_opcode,
)

from . import (
    logic,
)

UPDATED_OPCODES: Dict[int, OpcodeAPI] = {
    opcode_values.EXTCODESIZE: as_opcode(
        gas_cost=constants.GAS_NULL,
        logic_fn=logic.extcodesize_eip7702,
        mnemonic=mnemonics.EXTCODESIZE,
    ),
    opcode_values.EXTCODEHASH: as_opcode(
        gas_cost=constants.GAS_NULL,
        logic_fn=logic.extcodehash_eip7702,
        mnemonic=mnemonics.EXTCODEHASH,
    ),
    opcode_values.EXTCODECOPY: as_opcode(
        gas_cost=constants.GAS_NULL,
        logic_fn=logic.extcodecopy_eip7702,
        mnemonic=mnemonics.EXTCODECOPY,
    ),
    opcode_values.CALL: logic.CallEIP7702.configure(
        __name__="opcode:CALL",
        mnemonic=mnemonics.CALL,
        gas_cost=constants.GAS_NULL,
    )(),
    opcode_values.CALLCODE: logic.CallCodeEIP7702.configure(
        __name__="opcode:CALLCODE",
        mnemonic=mnemonics.CALLCODE,
        gas_cost=constants.GAS_NULL,
    )(),
    opcode_values.DELEGATECALL: logic.DelegateCallEIP7702.configure(
        __name__="opcode:DELEGATECALL",
        mnemonic=mnemonics.DELEGATECALL,
        gas_cost=constants.GAS_NULL,
    )(),
    opcode_values.STATICCALL: logic.StaticCallEIP7702.configure(
        __name__="opcode:STATICCALL",
        mnemonic=mnemonics.STATICCALL,
        gas_cost=constants.GAS_NULL,
    )(),
}
NEW_OPCODES: Dict[int, OpcodeAPI] = {}

PRAGUE_OPCODES: Dict[int, OpcodeAPI] = merge(
    copy.deepcopy(CANCUN_OPCODES),
    UPDATED_OPCODES,
    NEW_OPCODES,
)
