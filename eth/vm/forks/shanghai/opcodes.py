import copy
from typing import Dict

from eth.vm.opcode import as_opcode
from eth_utils.toolz import merge

from eth import constants
from eth.abc import OpcodeAPI
from eth.vm import mnemonics
from eth.vm import opcode_values
from eth.vm.logic import (
    stack,
)

from eth.vm.forks.paris.opcodes import PARIS_OPCODES


NEW_OPCODES = {
    opcode_values.PUSH0: as_opcode(
        logic_fn=stack.push0,
        mnemonic=mnemonics.PUSH0,
        gas_cost=constants.GAS_BASE,
    ),
}

SHANGHAI_OPCODES: Dict[int, OpcodeAPI] = merge(
    copy.deepcopy(PARIS_OPCODES),
    NEW_OPCODES
)
