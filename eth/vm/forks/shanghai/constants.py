from eth.vm.forks.spurious_dragon.constants import (
    EIP170_CODE_SIZE_LIMIT,
)

# https://eips.ethereum.org/EIPS/eip-3860
INITCODE_WORD_COST = 2
MAX_INITCODE_SIZE = EIP170_CODE_SIZE_LIMIT * 2
