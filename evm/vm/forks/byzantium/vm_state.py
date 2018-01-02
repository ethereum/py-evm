from evm.rlp.receipts import (
    Receipt,
)
from evm.vm.forks.frontier.vm_state import _make_frontier_receipt
from evm.vm.forks.spurious_dragon.vm_state import SpuriousDragonVMState

from .computation import ByzantiumComputation


class ByzantiumVMState(SpuriousDragonVMState):
    computation_class = ByzantiumComputation

    @staticmethod
    def make_receipt(vm_state, transaction, computation):
        old_receipt = _make_frontier_receipt(vm_state, transaction, computation)

        receipt = Receipt(
            state_root=b'' if computation.is_error else b'\x01',
            gas_used=old_receipt.gas_used,
            logs=old_receipt.logs,
        )
        return receipt
