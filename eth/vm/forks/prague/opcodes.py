import copy
from typing import (
    Dict,
)

from eth_utils.toolz import (
    merge,
)

from eth.abc import (
    OpcodeAPI,
)
from eth.vm.forks.cancun.opcodes import (
    CANCUN_OPCODES,
)

UPDATED_OPCODES: Dict[int, OpcodeAPI] = {}

NEW_OPCODES: Dict[int, OpcodeAPI] = {}

PRAGUE_OPCODES: Dict[int, OpcodeAPI] = merge(
    copy.deepcopy(CANCUN_OPCODES),
    UPDATED_OPCODES,
    NEW_OPCODES,
)
