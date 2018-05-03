
from evm.utils.hexadecimal import (
    encode_hex,
)
from evm.vm.forks.homestead.state import (
    HomesteadState,
)

from .blocks import SpuriousDragonBlock
from .computation import SpuriousDragonComputation
from .utils import collect_touched_accounts


class SpuriousDragonState(HomesteadState):
    block_class = SpuriousDragonBlock
    computation_class = SpuriousDragonComputation

    def run_post_computation(self, transaction, computation):
        computation = super().run_post_computation(transaction, computation)

        #
        # EIP161 state clearing
        #
        touched_accounts = collect_touched_accounts(computation)

        for account in touched_accounts:
            should_delete = (
                self.account_db.account_exists(account) and
                self.account_db.account_is_empty(account)
            )
            if should_delete:
                self.logger.debug(
                    "CLEARING EMPTY ACCOUNT: %s",
                    encode_hex(account),
                )
                self.account_db.delete_account(account)

        return computation
