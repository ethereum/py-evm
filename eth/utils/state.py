from typing import (
    Dict,
    Iterable,
    Tuple,
    Union,
)

from eth_utils import (
    to_tuple,
)

from eth_typing import (
Address,
)

from eth.db.account import (
    BaseAccountDB,
)


# Mapping from address to account state.
# 'balance', 'nonce' -> int
# 'code' -> bytes
# 'storage' -> Dict[int, int]
AccountState = Dict[Address, Dict[str, Union[int, bytes, Dict[int, int]]]]

DiffType = Iterable[Tuple[Address, str, Union[int, bytes], Union[int, bytes]]]

@to_tuple
def diff_account_db(expected_state: AccountState,
                    account_db: BaseAccountDB) -> DiffType:

    for account, account_data in sorted(expected_state.items()):
        assert isinstance(account_data['balance'], int)
        expected_balance = account_data['balance']

        assert isinstance(account_data['nonce'], int)
        expected_nonce = account_data['nonce']

        assert isinstance(account_data['code'], bytes)
        expected_code = account_data['code']

        actual_nonce = account_db.get_nonce(account)
        actual_code = account_db.get_code(account)
        actual_balance = account_db.get_balance(account)

        if actual_nonce != expected_nonce:
            yield (account, 'nonce', actual_nonce, expected_nonce)
        if actual_code != expected_code:
            yield (account, 'code', actual_code, expected_code)
        if actual_balance != expected_balance:
            yield (account, 'balance', actual_balance, expected_balance)

        assert isinstance(account_data['storage'], dict)
        for slot, expected_storage_value in sorted(account_data['storage'].items()):
            actual_storage_value = account_db.get_storage(account, slot)
            if actual_storage_value != expected_storage_value:
                yield (
                    account,
                    'storage[{0}]'.format(slot),
                    actual_storage_value,
                    expected_storage_value,
                )
