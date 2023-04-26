import copy

from eth.vm.forks.istanbul.opcodes import (
    ISTANBUL_OPCODES,
)

MUIR_GLACIER_OPCODES = copy.deepcopy(ISTANBUL_OPCODES)
