import copy
from eth_utils.toolz import (
    merge
)


UPDATED_OPCODES = {
}

ISTANBUL_OPCODES = merge(
    copy.deepcopy(CONSTANTINOPLE_OPCODES),
    UPDATED_OPCODES,
)
