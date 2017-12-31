
from evm.utils.hexadecimal import (
    encode_hex,
)
from evm.vm.forks.frontier.vm_state import (
    _execute_frontier_transaction,
)
from evm.vm.forks.homestead.vm_state import (
    HomesteadVMState,
)
from .utils import collect_touched_accounts


class SpuriousDragonVMState(HomesteadVMState):
    @staticmethod
    def execute_transaction(vm_state, transaction):
        computation = _execute_frontier_transaction(vm_state, transaction)

        #
        # EIP161 state clearing
        #
        touched_accounts = collect_touched_accounts(computation)

        with vm_state.state_db() as state_db:
            for account in touched_accounts:
                if state_db.account_exists(account) and state_db.account_is_empty(account):
                    vm_state.logger.debug(
                        "CLEARING EMPTY ACCOUNT: %s",
                        encode_hex(account),
                    )
                    state_db.delete_account(account)

        return computation
