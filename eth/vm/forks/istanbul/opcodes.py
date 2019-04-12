import copy
from eth_utils.toolz import (
    merge
)

from eth import (
    constants
)
from eth.vm import (
    mnemonics,
    opcode_values,
)
from eth.vm.forks.constantinople.opcodes import (
    CONSTANTINOPLE_OPCODES,
)
from eth.vm.logic import (
    context,
)
from eth.vm.opcode import (
    as_opcode
)


UPDATED_OPCODES = {
}

ISTANBUL_OPCODES = merge(
    copy.deepcopy(CONSTANTINOPLE_OPCODES),
    UPDATED_OPCODES,
)
