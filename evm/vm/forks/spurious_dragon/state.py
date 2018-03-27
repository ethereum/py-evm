
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

        with self.mutable_state_db() as state_db:
            for account in touched_accounts:
                if state_db.account_exists(account) and state_db.account_is_empty(account):
                    self.logger.debug(
                        "CLEARING EMPTY ACCOUNT: %s",
                        encode_hex(account),
                    )
                    state_db.delete_account(account)

        return computation
