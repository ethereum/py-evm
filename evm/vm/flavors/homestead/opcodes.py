import copy

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


HOMESTEAD_OPCODES = {
    **copy.deepcopy(FRONTIER_OPCODES),  # noqa: E999
    **UPDATED_OPCODES,
    **NEW_OPCODES
}
