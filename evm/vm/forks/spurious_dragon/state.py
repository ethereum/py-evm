
from evm.utils.hexadecimal import (
    encode_hex,
)
from evm.vm.forks.homestead.state import (
    HomesteadState,
    HomesteadTransactionExecutor,
)

from .computation import SpuriousDragonComputation
from .utils import collect_touched_accounts


class SpuriousDragonTransactionExecutor(HomesteadTransactionExecutor):
    def finalize_computation(self, transaction, computation):
        computation = super().finalize_computation(transaction, computation)

        #
        # EIP161 state clearing
        #
        touched_accounts = collect_touched_accounts(computation)

        for account in touched_accounts:
            should_delete = (
                self.vm_state.account_db.account_exists(account) and
                self.vm_state.account_db.account_is_empty(account)
            )
            if should_delete:
                self.vm_state.logger.debug(
                    "CLEARING EMPTY ACCOUNT: %s",
                    encode_hex(account),
                )
                self.vm_state.account_db.delete_account(account)

        return computation


class SpuriousDragonState(HomesteadState):
    computation_class = SpuriousDragonComputation
    computation_class = SpuriousDragonComputation
    transaction_executor = SpuriousDragonTransactionExecutor  # Type[BaseTransactionExecutor]
