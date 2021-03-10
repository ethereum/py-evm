from typing import Type

from eth.abc import (
    ComputationAPI,
    MessageAPI,
    SignedTransactionAPI,
    TransactionExecutorAPI,
)
from eth.vm.forks.muir_glacier.state import (
    MuirGlacierState
)
from eth.vm.forks.spurious_dragon.state import (
    SpuriousDragonTransactionExecutor,
)

from .computation import BerlinComputation


class BerlinTransactionExecutor(SpuriousDragonTransactionExecutor):
    def build_computation(
            self,
            message: MessageAPI,
            transaction: SignedTransactionAPI) -> ComputationAPI:
        self.vm_state.mark_address_warm(transaction.to)
        self.vm_state.mark_address_warm(transaction.sender)
        # TODO mark access list as warm
        return super().build_computation(message, transaction)


class BerlinState(MuirGlacierState):
    computation_class = BerlinComputation
    transaction_executor_class: Type[TransactionExecutorAPI] = BerlinTransactionExecutor
