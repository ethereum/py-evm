from evm.rlp.receipts import (
    Receipt,
)
from evm.vm.forks.frontier.vm_state import _make_frontier_receipt
from evm.vm.forks.spurious_dragon.vm_state import SpuriousDragonVMState

from .computation import ByzantiumComputation
from .constants import (
    EIP658_TRANSACTION_STATUS_CODE_FAILURE,
    EIP658_TRANSACTION_STATUS_CODE_SUCCESS,
)


class ByzantiumVMState(SpuriousDragonVMState):
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
