from typing import (
    Type,
)

from eth.abc import (
    ComputationAPI,
    MessageAPI,
    SignedTransactionAPI,
    TransactionContextAPI,
    TransactionExecutorAPI,
)
from eth.vm.forks.cancun import (
    CancunState,
)
from eth.vm.forks.cancun.state import (
    CancunTransactionExecutor,
)
from eth.vm.forks.prague.constants import (
    TOTAL_COST_FLOOR_PER_TOKEN,
)

from ..cancun.transaction_context import (
    CancunTransactionContext,
)
from .computation import (
    PragueComputation,
)


class PragueTransactionExecutor(CancunTransactionExecutor):
    def build_evm_message(self, transaction: SignedTransactionAPI) -> MessageAPI:
        if hasattr(transaction, "authorization_list"):
            message = super().build_evm_message(transaction)
            # TODO: 7702
            # message.authorizations = transaction.authorization_list
            return message
        else:
            return super().build_evm_message(transaction)

    def validate_eip7623_calldata_cost(
        self,
        transaction: SignedTransactionAPI,
        computation: ComputationAPI,
    ) -> None:
        gas_remaining = computation.get_gas_remaining()
        gas_used = transaction.gas - gas_remaining
        gas_refund = self.calculate_gas_refund(computation, gas_used)
        total_gas_used = transaction.gas - gas_remaining - gas_refund

        zeros_in_data = transaction.data.count(b"\x00")
        non_zeros_in_data = len(transaction.data) - zeros_in_data
        tokens_in_calldata = zeros_in_data + (non_zeros_in_data * 4)

        eip7623_gas = 21000 + TOTAL_COST_FLOOR_PER_TOKEN * tokens_in_calldata

        if total_gas_used < eip7623_gas:
            # consume up to the data floor gas cost
            computation.consume_gas(eip7623_gas - total_gas_used, reason="EIP-7623")

    def finalize_computation(
        self, transaction: SignedTransactionAPI, computation: ComputationAPI
    ) -> ComputationAPI:
        self.validate_eip7623_calldata_cost(transaction, computation)
        return super().finalize_computation(transaction, computation)


class PragueState(CancunState):
    computation_class = PragueComputation
    transaction_context_class: Type[TransactionContextAPI] = CancunTransactionContext
    transaction_executor_class: Type[TransactionExecutorAPI] = PragueTransactionExecutor
