import copy
from eth_utils.toolz import (
    merge
)

from eth.vm.forks.constantinople.opcodes import (
    CONSTANTINOPLE_OPCODES,
)


UPDATED_OPCODES = {
}

ISTANBUL_OPCODES = merge(
    copy.deepcopy(CONSTANTINOPLE_OPCODES),
    UPDATED_OPCODES,
)
