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
from eth.vm import (
    mnemonics,
    opcode_values,
)
from eth.vm.forks.berlin.opcodes import (
    BERLIN_OPCODES,
)
from eth.vm.forks.byzantium.opcodes import (
    ensure_no_static,
)
from eth.vm.logic import (
    block,
)
from eth.vm.opcode import (
    Opcode,
    as_opcode,
)

from . import (
    storage,
)

UPDATED_OPCODES: Dict[int, Opcode] = {
    opcode_values.BASEFEE: as_opcode(
        gas_cost=constants.GAS_BASE,
        logic_fn=block.basefee,
        mnemonic=mnemonics.BASEFEE,
    ),
    opcode_values.SSTORE: as_opcode(
        gas_cost=constants.GAS_NULL,
        logic_fn=ensure_no_static(storage.sstore_eip3529),
        mnemonic=mnemonics.SSTORE,
    ),
}


LONDON_OPCODES = merge(
    copy.deepcopy(BERLIN_OPCODES),
    UPDATED_OPCODES,
)
