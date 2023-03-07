import copy
from typing import Dict

from eth.tools._utils.deprecation import deprecate_method
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
    opcode_values.SELFDESTRUCT: deprecate_method(
        PARIS_OPCODES[opcode_values.SELFDESTRUCT],
        message=(
            f"{mnemonics.SELFDESTRUCT} opcode present in computation. This opcode is "
            "deprecated and a breaking change to its functionality is likely to come "
            "in the future."
        ),
    ),
}

SHANGHAI_OPCODES: Dict[int, OpcodeAPI] = merge(
    copy.deepcopy(PARIS_OPCODES),
    NEW_OPCODES,
)
