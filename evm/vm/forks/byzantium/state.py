from evm.constants import (
    MAX_UNCLE_DEPTH,
)
from evm.rlp.receipts import (
    Receipt,
)
from evm.validation import (
    validate_lte,
)
from evm.vm.forks.frontier.state import _make_frontier_receipt
from evm.vm.forks.spurious_dragon.state import SpuriousDragonState

from .blocks import ByzantiumBlock
from .computation import ByzantiumComputation
from .constants import (
    EIP649_BLOCK_REWARD,
    EIP658_TRANSACTION_STATUS_CODE_FAILURE,
    EIP658_TRANSACTION_STATUS_CODE_SUCCESS,
)


class ByzantiumState(SpuriousDragonState):
    block_class = ByzantiumBlock
    computation_class = ByzantiumComputation

    def make_receipt(self, transaction, computation):
        old_receipt = _make_frontier_receipt(self, transaction, computation)

        if computation.is_error:
            state_root = EIP658_TRANSACTION_STATUS_CODE_FAILURE
        else:
            state_root = EIP658_TRANSACTION_STATUS_CODE_SUCCESS

        receipt = Receipt(
            state_root=state_root,
            gas_used=old_receipt.gas_used,
            logs=old_receipt.logs,
        )
        return receipt

    @staticmethod
    def get_block_reward():
        return EIP649_BLOCK_REWARD

    @staticmethod
    def get_uncle_reward(block_number, uncle):
        block_number_delta = block_number - uncle.block_number
        validate_lte(block_number_delta, MAX_UNCLE_DEPTH)
        return (8 - block_number_delta) * EIP649_BLOCK_REWARD // 8
