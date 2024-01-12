from typing import (
    Type,
)

from eth_utils import (
    encode_hex,
)

from eth.abc import (
    ComputationAPI,
    SignedTransactionAPI,
    TransactionExecutorAPI,
)
from eth.vm.forks.homestead.state import (
    HomesteadState,
    HomesteadTransactionExecutor,
)

from ._utils import (
    collect_touched_accounts,
)
from .computation import (
    SpuriousDragonComputation,
)


class SpuriousDragonTransactionExecutor(HomesteadTransactionExecutor):
    def finalize_computation(
        self, transaction: SignedTransactionAPI, computation: ComputationAPI
    ) -> ComputationAPI:
        computation = super().finalize_computation(transaction, computation)

        #
        # EIP161 state clearing
        #
        touched_accounts = collect_touched_accounts(computation)

        for account in touched_accounts:
            should_delete = self.vm_state.account_exists(
                account
            ) and self.vm_state.account_is_empty(account)
            if should_delete:
                self.vm_state.logger.debug2(
                    f"CLEARING EMPTY ACCOUNT: {encode_hex(account)}"
                )
                self.vm_state.delete_account(account)

        return computation


class SpuriousDragonState(HomesteadState):
    computation_class: Type[ComputationAPI] = SpuriousDragonComputation
    transaction_executor_class: Type[
        TransactionExecutorAPI
    ] = SpuriousDragonTransactionExecutor
