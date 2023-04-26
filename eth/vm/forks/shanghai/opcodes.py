import copy
from typing import (
    Dict,
)

from eth_utils.toolz import (
    merge,
)

from eth import (
    constants,
)
from eth.abc import (
    OpcodeAPI,
)
from eth.tools._utils.deprecation import (
    deprecate_method,
)
from eth.vm import (
    mnemonics,
    opcode_values,
)
from eth.vm.forks.paris.opcodes import (
    PARIS_OPCODES,
)
from eth.vm.logic import (
    stack,
)
from eth.vm.opcode import (
    as_opcode,
)

from .logic import (
    Create2EIP3860,
    CreateEIP3860,
)

UPDATED_OPCODES: Dict[int, OpcodeAPI] = {
    opcode_values.CREATE: CreateEIP3860.configure(
        __name__="CreateEIP3860",
        mnemonic=mnemonics.CREATE,
        gas_cost=constants.GAS_CREATE,
    )(),
    opcode_values.CREATE2: Create2EIP3860.configure(
        __name__="Create2EIP3860",
        mnemonic=mnemonics.CREATE2,
        gas_cost=constants.GAS_CREATE,
    )(),
    opcode_values.SELFDESTRUCT: deprecate_method(
        PARIS_OPCODES[opcode_values.SELFDESTRUCT],
        message=(
            f"{mnemonics.SELFDESTRUCT} opcode present in computation. This opcode is "
            "deprecated and a breaking change to its functionality is likely to come "
            "in the future."
        ),
    ),
}

NEW_OPCODES: Dict[int, OpcodeAPI] = {
    opcode_values.PUSH0: as_opcode(
        logic_fn=stack.push0,
        mnemonic=mnemonics.PUSH0,
        gas_cost=constants.GAS_BASE,
    ),
}

SHANGHAI_OPCODES: Dict[int, OpcodeAPI] = merge(
    copy.deepcopy(PARIS_OPCODES),
    UPDATED_OPCODES,
    NEW_OPCODES,
)
