from evm.constants import MAX_UNCLE_DEPTH
from evm.validation import (
    validate_lte,
)
from evm.vm.forks.spurious_dragon import SpuriousDragonVM

from .constants import EIP649_BLOCK_REWARD
from .headers import (
    create_byzantium_header_from_parent,
    configure_byzantium_header,
    compute_byzantium_difficulty,
)
from .blocks import ByzantiumBlock
from .vm_state import ByzantiumVMState


def _byzantium_get_block_reward():
    return EIP649_BLOCK_REWARD


def _byzantium_get_uncle_reward(block_number, uncle):
    validate_lte(uncle.block_number, MAX_UNCLE_DEPTH)
    block_number_delta = block_number - uncle.block_number
    return (8 - block_number_delta) * EIP649_BLOCK_REWARD // 8


ByzantiumVM = SpuriousDragonVM.configure(
    name='ByzantiumVM',
    # classes
    _block_class=ByzantiumBlock,
    _state_class=ByzantiumVMState,
    # Methods
    create_header_from_parent=staticmethod(create_byzantium_header_from_parent),
    compute_difficulty=staticmethod(compute_byzantium_difficulty),
    configure_header=configure_byzantium_header,
    get_block_reward=staticmethod(_byzantium_get_block_reward),
    get_uncle_reward=staticmethod(_byzantium_get_uncle_reward),
)
