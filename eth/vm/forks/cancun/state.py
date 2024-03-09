from typing import (
    Type,
)

from eth_utils import (
    ValidationError,
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
    BLOB_TX_TYPE,
    GAS_PER_BLOB,
    MIN_BLOB_BASE_FEE,
    VERSIONED_HASH_VERSION_KZG,
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

    def validate_transaction(self, transaction: SignedTransactionAPI) -> None:
        super().validate_transaction(transaction)

        # modify the check for sufficient balance
        max_total_fee = transaction.gas * transaction.max_fee_per_gas
        if transaction.type_id == BLOB_TX_TYPE:
            max_total_fee += (
                get_total_blob_gas(transaction) * transaction.max_fee_per_blob_gas
            )
        if self.get_balance(transaction.sender) < max_total_fee:
            raise ValidationError("Sender has insufficient funds for blob fee.")

        # add validity logic specific to blob txs
        if transaction.type_id == BLOB_TX_TYPE:
            # there must be at least one blob
            if len(transaction.blob_versioned_hashes) == 0:
                raise ValidationError(
                    "Blob transaction must contain at least one blob."
                )

            # all versioned blob hashes must start with VERSIONED_HASH_VERSION_KZG
            for h in transaction.blob_versioned_hashes:
                if h[0].to_bytes() != VERSIONED_HASH_VERSION_KZG:
                    raise ValidationError(
                        "Blob versioned hash does not start with expected "
                        f"KZG version: {VERSIONED_HASH_VERSION_KZG}"
                    )

            # ensure that the user was willing to at least pay the current
            # blob base fee
            if transaction.max_fee_per_blob_gas < self.blob_base_fee:
                raise ValidationError(
                    "Blob transaction must pay at least the current blob base fee."
                )
