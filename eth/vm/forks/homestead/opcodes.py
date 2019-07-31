import copy
from typing import Dict

from eth_utils.toolz import merge

from eth import constants
from eth.abc import OpcodeAPI
from eth.vm import mnemonics
from eth.vm import opcode_values
from eth.vm.logic import (
    call,
)

from eth.vm.forks.frontier.opcodes import FRONTIER_OPCODES


NEW_OPCODES = {
    opcode_values.DELEGATECALL: call.DelegateCall.configure(
        __name__='opcode:DELEGATECALL',
        mnemonic=mnemonics.DELEGATECALL,
        gas_cost=constants.GAS_CALL,
    )(),
}


HOMESTEAD_OPCODES: Dict[int, OpcodeAPI] = merge(
    copy.deepcopy(FRONTIER_OPCODES),
    NEW_OPCODES
)
