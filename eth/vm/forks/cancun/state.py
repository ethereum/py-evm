from typing import (
    Type,
)

from eth.abc import (
    ComputationAPI,
    SignedTransactionAPI,
    StateAPI,
    TransactionContextAPI,
    TransactionExecutorAPI,
    TransactionFieldsAPI,
)

from ..shanghai import (
    ShanghaiState,
)
from ..shanghai.state import (
    ShanghaiTransactionExecutor,
)
from .computation import (
    CancunComputation,
)
from .constants import (
    BLOB_BASE_FEE_UPDATE_FRACTION,
    GAS_PER_BLOB,
    MIN_BLOB_BASE_FEE,
)


def fake_exponential(factor: int, numerator: int, denominator: int) -> int:
    i = 1
    output = 0
    numerator_accum = factor * denominator
    while numerator_accum > 0:
        output += numerator_accum
        numerator_accum = (numerator_accum * numerator) // (denominator * i)
        i += 1
    return output // denominator


def get_total_blob_gas(transaction: TransactionFieldsAPI) -> int:
    if hasattr(transaction, "blob_versioned_hashes"):
        return GAS_PER_BLOB * len(transaction.blob_versioned_hashes)

    return 0


class CancunTransactionExecutor(ShanghaiTransactionExecutor):
    def calc_data_fee(self, transaction: TransactionFieldsAPI) -> int:
        return get_total_blob_gas(transaction) * self.vm_state.blob_base_fee

    def finalize_computation(
        self, transaction: SignedTransactionAPI, computation: ComputationAPI
    ) -> ComputationAPI:
        computation = super().finalize_computation(transaction, computation)

        data_fee = self.calc_data_fee(transaction)
        computation.state.delta_balance(transaction.sender, -1 * data_fee)

        return computation


class CancunState(ShanghaiState):
    computation_class = CancunComputation
    transaction_executor_class: Type[TransactionExecutorAPI] = CancunTransactionExecutor

    def get_transaction_context(
        self: StateAPI, transaction: SignedTransactionAPI
    ) -> TransactionContextAPI:
        context = super().get_transaction_context(transaction)

        if hasattr(transaction, "blob_versioned_hashes"):
            context.excess_blob_gas = (
                len(transaction.blob_versioned_hashes) * GAS_PER_BLOB
            )
        return context

    @property
    def blob_base_fee(self) -> int:
        excess_blob_gas = self.execution_context.excess_blob_gas
        return fake_exponential(
            MIN_BLOB_BASE_FEE, excess_blob_gas, BLOB_BASE_FEE_UPDATE_FRACTION
        )
