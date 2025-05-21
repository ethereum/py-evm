import copy

from eth_utils.toolz import merge


from eth.vm.forks.petersburg.opcodes import (
    PETERSBURG_OPCODES,
)


UPDATED_OPCODES: Dict[int, eth.vm.opcode.Opcode] = {
    # New opcodes
}

ISTANBUL_OPCODES = merge(
    copy.deepcopy(PETERSBURG_OPCODES),
    UPDATED_OPCODES,
)
