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
from eth.vm.forks.byzantium.opcodes import (
    ensure_no_static,
)
from eth.vm.forks.shanghai.opcodes import (
    SHANGHAI_OPCODES,
)
from eth.vm.forks.tangerine_whistle.constants import (
    GAS_SELFDESTRUCT_EIP150,
)
from eth.vm.logic import (
    block,
    context,
    memory,
)
from eth.vm.opcode import (
    as_opcode,
)

from . import (
    constants as cancun_constants,
    logic as cancun_logic,
)

UPDATED_OPCODES: Dict[int, OpcodeAPI] = {
    opcode_values.SELFDESTRUCT: deprecate_method(
        as_opcode(
            logic_fn=ensure_no_static(cancun_logic.selfdestruct_eip6780),
            mnemonic=mnemonics.SELFDESTRUCT,
            gas_cost=GAS_SELFDESTRUCT_EIP150,
        ),
        message=(
            f"{mnemonics.SELFDESTRUCT} opcode present in computation. This opcode is "
            "deprecated and a breaking change to its functionality is likely to come "
            "in the future."
        ),
    )
}

NEW_OPCODES: Dict[int, OpcodeAPI] = {
    opcode_values.MCOPY: as_opcode(
        logic_fn=memory.mcopy,
        mnemonic=mnemonics.MCOPY,
        gas_cost=constants.GAS_VERYLOW,
    ),
    opcode_values.TLOAD: as_opcode(
        logic_fn=cancun_logic.tload,
        mnemonic=mnemonics.TLOAD,
        gas_cost=cancun_constants.TLOAD_COST,
    ),
    opcode_values.TSTORE: as_opcode(
        logic_fn=cancun_logic.tstore,
        mnemonic=mnemonics.TSTORE,
        gas_cost=cancun_constants.TSTORE_COST,
    ),
    opcode_values.BLOBHASH: as_opcode(
        logic_fn=context.blob_hash,
        mnemonic=mnemonics.BLOBHASH,
        gas_cost=cancun_constants.HASH_OPCODE_GAS,
    ),
    opcode_values.BLOBBASEFEE: as_opcode(
        logic_fn=block.blob_base_fee,
        mnemonic=mnemonics.BLOBBASEFEE,
        gas_cost=cancun_constants.BASEFEE_OPCODE_GAS,
    ),
}

CANCUN_OPCODES: Dict[int, OpcodeAPI] = merge(
    copy.deepcopy(SHANGHAI_OPCODES),
    UPDATED_OPCODES,
    NEW_OPCODES,
)
