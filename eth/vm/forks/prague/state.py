from typing import (
    Type,
)

from eth.abc import (
    MessageAPI,
    SignedTransactionAPI,
    TransactionExecutorAPI,
)
from eth.vm.forks.cancun import (
    CancunState,
)
from eth.vm.forks.cancun.state import (
    CancunTransactionExecutor,
)

from .computation import (
    PragueComputation,
)


class PragueTransactionExecutor(CancunTransactionExecutor):
    def build_evm_message(self, transaction: SignedTransactionAPI) -> MessageAPI:
        if hasattr(transaction, "authorization_list"):
            message = super().build_evm_message(transaction)
            message.authorizations = transaction.authorization_list
            return message
        else:
            return super().build_evm_message(transaction)


class PragueState(CancunState):
    computation_class = PragueComputation
    transaction_executor_class: Type[TransactionExecutorAPI] = PragueTransactionExecutor
