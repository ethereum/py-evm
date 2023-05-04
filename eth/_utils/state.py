from eth_utils import (
    to_tuple,
)

from eth.typing import (
    AccountDiff,
    AccountState,
)
from eth.vm.state import (
    BaseState,
)


@to_tuple
def diff_state(expected_state: AccountState, state: BaseState) -> AccountDiff:
    for account, account_data in sorted(expected_state.items()):
        expected_balance = account_data["balance"]
        expected_nonce = account_data["nonce"]
        expected_code = account_data["code"]

        actual_nonce = state.get_nonce(account)
        actual_code = state.get_code(account)
        actual_balance = state.get_balance(account)

        if actual_nonce != expected_nonce:
            yield (account, "nonce", actual_nonce, expected_nonce)
        if actual_code != expected_code:
            yield (account, "code", actual_code, expected_code)
        if actual_balance != expected_balance:
            yield (account, "balance", actual_balance, expected_balance)

        for slot, expected_storage_value in sorted(account_data["storage"].items()):
            actual_storage_value = state.get_storage(account, slot)
            if actual_storage_value != expected_storage_value:
                yield (
                    account,
                    f"storage[{slot}]",
                    actual_storage_value,
                    expected_storage_value,
                )
