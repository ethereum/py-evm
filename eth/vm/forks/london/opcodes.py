import copy
from typing import Dict

from eth_utils.toolz import merge

from eth.vm.logic import (
    block,
)
from eth.vm import (
    mnemonics,
    opcode_values,
)
from eth.vm.opcode import (
    Opcode,
    as_opcode,
)
from eth import constants

from eth.vm.forks.berlin.opcodes import (
    BERLIN_OPCODES,
)


UPDATED_OPCODES: Dict[int, Opcode] = {
    opcode_values.BASEFEE: as_opcode(
        gas_cost=constants.GAS_BASE,
        logic_fn=block.basefee,
        mnemonic=mnemonics.BASEFEE,
    ),
}


LONDON_OPCODES = merge(
    copy.deepcopy(BERLIN_OPCODES),
    UPDATED_OPCODES,
)
