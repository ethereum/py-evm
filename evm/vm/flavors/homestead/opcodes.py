import copy

from toolz import merge

from evm import constants
from evm import opcode_values
from evm import mnemonics

from evm.logic import (
    call,
)

from evm.vm.flavors.frontier.opcodes import FRONTIER_OPCODES


NEW_OPCODES = {
    opcode_values.DELEGATECALL: call.DelegateCall.configure(
        name='opcode:DELEGATECALL',
        mnemonic=mnemonics.DELEGATECALL,
        gas_cost=constants.GAS_CALL,
    )(),
}


UPDATED_OPCODES = {
    # TODO: suicide?
}


HOMESTEAD_OPCODES = merge(
    copy.deepcopy(FRONTIER_OPCODES),
    UPDATED_OPCODES,
    NEW_OPCODES,
)
