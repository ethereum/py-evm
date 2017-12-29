from evm.utils.hexadecimal import (
    encode_hex,
)

from ..frontier import _execute_frontier_transaction
from ..homestead import HomesteadVM

from .blocks import SpuriousDragonBlock
from .computation import SpuriousDragonComputation
from .opcodes import SPURIOUS_DRAGON_OPCODES
from .utils import collect_touched_accounts


def _execute_spurious_dragon_transaction(vm, transaction):
    computation = _execute_frontier_transaction(vm, transaction)

    #
    # EIP161 state clearing
    #
    touched_accounts = collect_touched_accounts(computation)

    with vm.state.state_db() as state_db:
        for account in touched_accounts:
            if state_db.account_exists(account) and state_db.account_is_empty(account):
                vm.logger.debug(
                    "CLEARING EMPTY ACCOUNT: %s",
                    encode_hex(account),
                )
                state_db.delete_account(account)

    return computation


SpuriousDragonVM = HomesteadVM.configure(
    name='SpuriousDragonVM',
    # rlp classes
    _block_class=SpuriousDragonBlock,
    _computation_class=SpuriousDragonComputation,
    # opcodes
    opcodes=SPURIOUS_DRAGON_OPCODES,
    execute_transaction=_execute_spurious_dragon_transaction,
)
