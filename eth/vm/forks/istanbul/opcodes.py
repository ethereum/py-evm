import copy

from eth_utils.toolz import merge

from eth import constants
from eth.vm import (
    mnemonics,
    opcode_values,
)
from eth.vm.forks.byzantium.opcodes import (
    ensure_no_static
)
from eth.vm.forks.constantinople.opcodes import (
    CONSTANTINOPLE_OPCODES,
)
from eth.vm.opcode import as_opcode
from .storage import (
    sstore_eip2200,
)


UPDATED_OPCODES = {
    # Repriced opcodes
    opcode_values.SSTORE: as_opcode(
        logic_fn=ensure_no_static(sstore_eip2200),
        mnemonic=mnemonics.SSTORE,
        gas_cost=constants.GAS_NULL,
    ),
}

ISTANBUL_OPCODES = merge(
    copy.deepcopy(CONSTANTINOPLE_OPCODES),
    UPDATED_OPCODES,
)
