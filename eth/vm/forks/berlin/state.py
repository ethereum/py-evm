from typing import (
    Type,
)

from eth.abc import (
    MessageAPI,
    MessageComputationAPI,
    SignedTransactionAPI,
    TransactionExecutorAPI,
)
from eth.vm.forks.muir_glacier.state import (
    MuirGlacierState,
)
from eth.vm.forks.spurious_dragon.state import (
    SpuriousDragonTransactionExecutor,
)

from .computation import (
    BerlinMessageComputation,
)


class BerlinTransactionExecutor(SpuriousDragonTransactionExecutor):
    def build_computation(
            self,
            message: MessageAPI,
            transaction: SignedTransactionAPI) -> MessageComputationAPI:

        self.vm_state.mark_address_warm(transaction.sender)

        # Mark recipient as accessed, or the new contract being created
        self.vm_state.mark_address_warm(message.storage_address)

        for address, slots in transaction.access_list:
            self.vm_state.mark_address_warm(address)
            for slot in slots:
                self.vm_state.mark_storage_warm(address, slot)

        return super().build_computation(message, transaction)


class BerlinState(MuirGlacierState):
    message_computation_class = BerlinMessageComputation
    transaction_executor_class: Type[TransactionExecutorAPI] = BerlinTransactionExecutor
