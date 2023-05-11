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
from eth.vm.forks.london.opcodes import (
    LONDON_OPCODES,
)
from eth.vm.logic import (
    block,
)
from eth.vm.opcode import (
    as_opcode,
)

NEW_OPCODES = {
    # EIP-4399: supplant DIFFICULTY with PREVRANDAO
    opcode_values.PREVRANDAO: as_opcode(
        logic_fn=block.mixhash,
        mnemonic=mnemonics.PREVRANDAO,
        gas_cost=constants.GAS_BASE,
    ),
}

PARIS_OPCODES: Dict[int, OpcodeAPI] = merge(copy.deepcopy(LONDON_OPCODES), NEW_OPCODES)
