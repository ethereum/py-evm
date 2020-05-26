import copy

from eth_utils.toolz import merge


from eth.vm.forks.muir_glacier.opcodes import (
    MUIR_GLACIER_OPCODES,
)


UPDATED_OPCODES = {
    # New opcodes
}

BERLIN_OPCODES = merge(
    copy.deepcopy(MUIR_GLACIER_OPCODES),
    UPDATED_OPCODES,
)
