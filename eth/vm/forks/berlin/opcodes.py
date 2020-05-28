import copy
from typing import Dict

from eth_utils.toolz import merge

from eth.vm.forks.muir_glacier.opcodes import (
    MUIR_GLACIER_OPCODES,
)
from eth.vm.opcode import Opcode


UPDATED_OPCODES: Dict[int, Opcode] = {
    # New opcodes
}

BERLIN_OPCODES = merge(
    copy.deepcopy(MUIR_GLACIER_OPCODES),
    UPDATED_OPCODES,
)
import copy

from eth_utils.toolz import merge

from eth import constants
from eth.vm import (
    mnemonics,
    opcode_values,
)
from eth.vm.opcode import as_opcode
from eth.vm.logic import flow

UPDATED_OPCODES = {
    opcode_values.BEGINSUB: as_opcode(
        logic_fn=flow.beginsub,
        mnemonic=mnemonics.BEGINSUB,
        gas_cost=constants.GAS_BASE,
    ),
    opcode_values.JUMPSUB: as_opcode(
        logic_fn=flow.jumpsub,
        mnemonic=mnemonics.JUMPSUB,
        gas_cost=constants.GAS_HIGH,
    ),
    opcode_values.RETURNSUB: as_opcode(
        logic_fn=flow.returnsub,
        mnemonic=mnemonics.RETURNSUB,
        gas_cost=constants.GAS_LOW,
    ),
}

BERLIN_OPCODES = merge(
    copy.deepcopy(MUIR_GLACIER_OPCODES),
    UPDATED_OPCODES,
)
