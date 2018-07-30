import copy
from cytoolz import (
    merge
)

from eth import (
    constants
)
from eth.vm import (
    mnemonics,
    opcode_values,
)
from eth.vm.forks.byzantium.opcodes import (
    BYZANTIUM_OPCODES
)
from eth.vm.logic import (
    arithmetic
)
from eth.vm.opcode import (
    as_opcode
)


UPDATED_OPCODES = {
    opcode_values.SHL: as_opcode(
        logic_fn=arithmetic.shl,
        mnemonic=mnemonics.SHL,
        gas_cost=constants.GAS_VERYLOW,
    ),
}

CONSTANTINOPLE_OPCODES = merge(
    copy.deepcopy(BYZANTIUM_OPCODES),
    UPDATED_OPCODES,
)
