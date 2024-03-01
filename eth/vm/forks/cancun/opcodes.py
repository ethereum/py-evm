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

UPDATED_OPCODES: Dict[int, OpcodeAPI] = {}

NEW_OPCODES: Dict[int, OpcodeAPI] = {
    opcode_values.MCOPY: as_opcode(
        logic_fn=memory.mcopy,
        mnemonic=mnemonics.MCOPY,
        gas_cost=constants.GAS_VERYLOW + constants.GAS_COPY,
    ),
}

CANCUN_OPCODES: Dict[int, OpcodeAPI] = merge(
    copy.deepcopy(SHANGHAI_OPCODES),
    UPDATED_OPCODES,
    NEW_OPCODES,
)
