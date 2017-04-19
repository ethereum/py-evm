import copy

from tools import merge

from evm import constants
from evm import opcode_values
from evm import mnemonics

from evm.opcode import as_opcode
from evm.logic import (
    system,
)

from evm.vm.flavors.frontier.opcodes import FRONTIER_OPCODES


NEW_OPCODES = {
    opcode_values.DELEGATECALL: as_opcode(
        logic_fn=system.delegatecall,
        mnemonic=mnemonics.DELEGATECALL,
        gas_cost=constants.GAS_CALL,
    ),
}


UPDATED_OPCODES = {
    # TODO: suicide?
}


HOMESTEAD_OPCODES = merge(
    copy.deepcopy(FRONTIER_OPCODES),
    UPDATED_OPCODES,
    NEW_OPCODES,
)
