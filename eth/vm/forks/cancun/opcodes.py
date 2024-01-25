import copy
from typing import (
    Dict,
)

from eth_utils.toolz import (
    merge,
)

from eth.abc import (
    OpcodeAPI,
)
from eth.vm import (
    mnemonics,
    opcode_values,
)
from eth.vm.forks.shanghai.opcodes import (
    SHANGHAI_OPCODES,
)
from eth.vm.opcode import (
    as_opcode,
)

from .constants import (
    TLOAD_GAS_COST,
    TSTORE_GAS_COST,
)

NEW_OPCODES: Dict[int, OpcodeAPI] = {
    opcode_values.TLOAD: as_opcode(
        gas_cost=TLOAD_GAS_COST,
        logic_fn=None,  # TODO: add logic function
        mnemonic=mnemonics.TLOAD,
    ),
    opcode_values.TSTORE: as_opcode(
        gas_cost=TSTORE_GAS_COST,
        logic_fn=None,  # TODO: add logic function
        mnemonic=mnemonics.TSTORE,
    ),
}

CANCUN_OPCODES: Dict[int, OpcodeAPI] = merge(
    copy.deepcopy(SHANGHAI_OPCODES),
    NEW_OPCODES,
)
