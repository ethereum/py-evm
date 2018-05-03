from evm.constants import (
    MAX_UNCLE_DEPTH,
)
from evm.validation import (
    validate_lte,
)
from evm.vm.forks.spurious_dragon.state import SpuriousDragonState

from .blocks import ByzantiumBlock
from .computation import ByzantiumComputation
from .constants import (
    EIP649_BLOCK_REWARD,
)


class ByzantiumState(SpuriousDragonState):
    block_class = ByzantiumBlock
    computation_class = ByzantiumComputation

    @staticmethod
    def get_block_reward():
        return EIP649_BLOCK_REWARD

    @staticmethod
    def get_uncle_reward(block_number, uncle):
        block_number_delta = block_number - uncle.block_number
        validate_lte(block_number_delta, MAX_UNCLE_DEPTH)
        return (8 - block_number_delta) * EIP649_BLOCK_REWARD // 8
