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

from . import (
    logic as prague_logic,
)

UPDATED_OPCODES: Dict[int, OpcodeAPI] = {
    opcode_values.CALL: prague_logic.CallEIP7702.configure(
        __name__="opcode:CALL",
        mnemonic=mnemonics.CALL,
        gas_cost=constants.GAS_NULL,
    )(),
    opcode_values.CALLCODE: prague_logic.CallCodeEIP7702.configure(
        __name__="opcode:CALLCODE",
        mnemonic=mnemonics.CALLCODE,
        gas_cost=constants.GAS_NULL,
    )(),
    opcode_values.DELEGATECALL: prague_logic.DelegateCallEIP7702.configure(
        __name__="opcode:DELEGATECALL",
        mnemonic=mnemonics.DELEGATECALL,
        gas_cost=constants.GAS_NULL,
    )(),
    opcode_values.STATICCALL: prague_logic.StaticCallEIP7702.configure(
        __name__="opcode:STATICCALL",
        mnemonic=mnemonics.STATICCALL,
        gas_cost=constants.GAS_NULL,
    )(),
}

PRAGUE_OPCODES: Dict[int, OpcodeAPI] = merge(
    copy.deepcopy(CANCUN_OPCODES),
    UPDATED_OPCODES,
)
