import copy

from eth.vm.forks.constantinople.opcodes import (
    CONSTANTINOPLE_OPCODES,
)


ISTANBUL_OPCODES = copy.deepcopy(CONSTANTINOPLE_OPCODES)
