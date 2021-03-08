import copy
from typing import Dict

from eth_utils.toolz import merge

from eth.vm import (
    mnemonics,
    opcode_values,
)
from eth.vm.opcode import (
    Opcode,
    as_opcode,
)
from eth import constants

from eth.vm.forks.muir_glacier.opcodes import (
    MUIR_GLACIER_OPCODES,
)
from eth.vm.logic import (
    context,
)


UPDATED_OPCODES: Dict[int, Opcode] = {
    opcode_values.BALANCE: as_opcode(
        gas_cost=constants.GAS_NULL,
        logic_fn=context.balance_eip_2929,
        mnemonic=mnemonics.BALANCE,
    ),
}


BERLIN_OPCODES = merge(
    copy.deepcopy(MUIR_GLACIER_OPCODES),
    UPDATED_OPCODES,
)
