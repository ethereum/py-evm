from typing import (  # noqa: F401
    Type,
)

from evm.constants import (
    MAX_UNCLE_DEPTH,
)
from evm.rlp.blocks import BaseBlock  # noqa: F401
from evm.validation import (
    validate_lte,
)
from evm.vm.forks.spurious_dragon import SpuriousDragonVM
from evm.vm.forks.frontier import make_frontier_receipt
from evm.vm.state import BaseState  # noqa: F401

from .blocks import ByzantiumBlock
from .constants import (
    EIP649_BLOCK_REWARD,
    EIP658_TRANSACTION_STATUS_CODE_FAILURE,
    EIP658_TRANSACTION_STATUS_CODE_SUCCESS,
)
from .headers import (
    create_byzantium_header_from_parent,
    configure_byzantium_header,
    compute_byzantium_difficulty,
)
from .state import ByzantiumState


def make_byzantium_receipt(base_header, transaction, computation, state):
    frontier_receipt = make_frontier_receipt(base_header, transaction, computation, state)

    if computation.is_error:
        status_code = EIP658_TRANSACTION_STATUS_CODE_FAILURE
    else:
        status_code = EIP658_TRANSACTION_STATUS_CODE_SUCCESS

    return frontier_receipt.copy(state_root=status_code)


class ByzantiumVM(SpuriousDragonVM):
    # fork name
    fork = 'byzantium'

    # classes
    block_class = ByzantiumBlock  # type: Type[BaseBlock]
    _state_class = ByzantiumState  # type: Type[BaseState]

    # Methods
    create_header_from_parent = staticmethod(create_byzantium_header_from_parent)
    compute_difficulty = staticmethod(compute_byzantium_difficulty)
    configure_header = configure_byzantium_header
    make_receipt = staticmethod(make_byzantium_receipt)

    @staticmethod
    def get_block_reward():
        return EIP649_BLOCK_REWARD

    @staticmethod
    def get_uncle_reward(block_number, uncle):
        block_number_delta = block_number - uncle.block_number
        validate_lte(block_number_delta, MAX_UNCLE_DEPTH)
        return (8 - block_number_delta) * EIP649_BLOCK_REWARD // 8
