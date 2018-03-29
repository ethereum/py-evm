import copy

from cytoolz import merge

from evm import constants
from evm.vm import mnemonics
from evm.vm import opcode_values
from evm.vm.logic import (
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
