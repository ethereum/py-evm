import copy

from cytoolz import merge

from evm import constants
from evm import opcode_values
from evm import mnemonics

from evm.logic import (
    call,
)

from evm.vm.forks.frontier.opcodes import FRONTIER_OPCODES


NEW_OPCODES = {
    opcode_values.DELEGATECALL: call.DelegateCall.configure(
        __name__='opcode:DELEGATECALL',
        mnemonic=mnemonics.DELEGATECALL,
        gas_cost=constants.GAS_CALL,
    )(),
}


HOMESTEAD_OPCODES = merge(
    copy.deepcopy(FRONTIER_OPCODES),
    NEW_OPCODES
)
