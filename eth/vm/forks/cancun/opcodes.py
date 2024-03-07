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
from eth.vm.forks.shanghai.opcodes import (
    SHANGHAI_OPCODES,
)
from eth.vm.logic import (
    memory,
)
from eth.vm.opcode import (
    as_opcode,
)

from . import (
    constants as cancun_constants,
    logic as cancun_logic,
)

UPDATED_OPCODES: Dict[int, OpcodeAPI] = {}

NEW_OPCODES: Dict[int, OpcodeAPI] = {
    opcode_values.MCOPY: as_opcode(
        logic_fn=memory.mcopy,
        mnemonic=mnemonics.MCOPY,
        gas_cost=constants.GAS_VERYLOW,
    ),
    opcode_values.TLOAD: as_opcode(
        logic_fn=cancun_logic.tload,
        mnemonic=mnemonics.TLOAD,
        gas_cost=cancun_constants.TLOAD_COST,
    ),
    opcode_values.TSTORE: as_opcode(
        logic_fn=cancun_logic.tstore,
        mnemonic=mnemonics.TSTORE,
        gas_cost=cancun_constants.TSTORE_COST,
    ),
}

CANCUN_OPCODES: Dict[int, OpcodeAPI] = merge(
    copy.deepcopy(SHANGHAI_OPCODES),
    UPDATED_OPCODES,
    NEW_OPCODES,
)
