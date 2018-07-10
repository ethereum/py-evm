from eth_utils import (
    to_tuple,
)


@to_tuple
def diff_account_db(expected_state, account_db):
    for account, account_data in sorted(expected_state.items()):
        expected_nonce = account_data['nonce']
        expected_code = account_data['code']
        expected_balance = account_data['balance']

        actual_nonce = account_db.get_nonce(account)
        actual_code = account_db.get_code(account)
        actual_balance = account_db.get_balance(account)

        if actual_nonce != expected_nonce:
            yield (account, 'nonce', actual_nonce, expected_nonce)
        if actual_code != expected_code:
            yield (account, 'code', actual_code, expected_code)
        if actual_balance != expected_balance:
            yield (account, 'balance', actual_balance, expected_balance)

        for slot, expected_storage_value in sorted(account_data['storage'].items()):
            actual_storage_value = account_db.get_storage(account, slot)
            if actual_storage_value != expected_storage_value:
                yield (
                    account,
                    'storage[{0}]'.format(slot),
                    actual_storage_value,
                    expected_storage_value,
                )
