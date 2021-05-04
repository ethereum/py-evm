from eth_utils.exceptions import ValidationError
from eth.vm.forks.london.blocks import LondonBlockHeader
from typing import Type

from eth.abc import (
    AccountDatabaseAPI,
    ComputationAPI,
    MessageAPI,
    SignedTransactionAPI,
    TransactionExecutorAPI,
)
from eth.constants import (
    SECPK1_N,
)
from eth.db.account import (
    AccountDB
)
from eth.vm.forks.berlin.state import (
    BerlinState,
    BerlinTransactionExecutor,
)

from .computation import LondonComputation
from .transactions import normalize_transaction
from .validation import validate_london_normalized_transaction


class LondonTransactionExecutor(BerlinTransactionExecutor):
    def __call__(self, transaction: SignedTransactionAPI) -> ComputationAPI:
        # unlike other VMs, don't validate tx here -- we need access to both header and state
        message = self.build_evm_message(transaction)
        computation = self.build_computation(message, transaction)
        finalized_computation = self.finalize_computation(transaction, computation)
        return finalized_computation


class LondonState(BerlinState):
    account_db_class: Type[AccountDatabaseAPI] = AccountDB
    computation_class = LondonComputation
    transaction_executor_class: Type[TransactionExecutorAPI] = LondonTransactionExecutor

    def apply_transaction(
            self,
            transaction: SignedTransactionAPI,
            header: LondonBlockHeader
        ) -> ComputationAPI:

        self.validate_transaction(transaction, header)
        executor = self.get_transaction_executor()
        return executor(transaction)

    def validate_transaction(
        self,
        transaction: SignedTransactionAPI,
        header: LondonBlockHeader
    ) -> None:

        # homestead validation
        if transaction.s > SECPK1_N // 2 or transaction.s == 0:
            raise ValidationError("Invalid signature S value")

        normalized_transaction = normalize_transaction(transaction)
        validate_london_normalized_transaction(
            state=self, transaction=normalized_transaction, header=header
        )
