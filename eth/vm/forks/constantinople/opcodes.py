import copy

from eth.vm.forks.byzantium.opcodes import (
    BYZANTIUM_OPCODES
)


CONSTANTINOPLE_OPCODES = copy.deepcopy(BYZANTIUM_OPCODES)
