import pytest

import json
import os

from eth_utils import (
    to_canonical_address,
    encode_hex,
    decode_hex,
)

from evm.storage.memory import (
    MemoryStorage,
)
from evm.vm import (
    Message,
    EVM,
    execute_vm,
)

from evm.utils.numeric import (
    big_endian_to_int,
)


ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(__file__))


ARITHMETIC_FIXTURES_PATH = os.path.join(
    ROOT_PROJECT_DIR,
    'fixtures',
    'VMTests',
    'vmArithmeticTest.json',
)


with open(ARITHMETIC_FIXTURES_PATH) as arithmetic_fixtures_file:
    RAW_ARITHMETIC_FIXTURES = json.load(arithmetic_fixtures_file)


ARITHMETIC_FIXTURES = tuple(
    RAW_ARITHMETIC_FIXTURES[key]
    for key in sorted(RAW_ARITHMETIC_FIXTURES.keys())
)


@pytest.mark.parametrize(
    'fixture', ARITHMETIC_FIXTURES,
)
def test_vm_using_fixture(fixture):
    evm = EVM(MemoryStorage())

    assert fixture['callcreates'] == []

    for account_as_hex, account_data in fixture['pre'].items():
        account = to_canonical_address(account_as_hex)

        for slot_as_hex, value_as_hex in account_data['storage'].items():
            slot = int(slot_as_hex, 16)
            value = decode_hex(value)

            evm.storage.set_storage(account, slot, value)

        nonce = int(account_data['nonce'], 16)
        code = decode_hex(account_data['code'])
        balance = int(account_data['balance'], 16)

        evm.storage.set_nonce(account, nonce)
        evm.storage.set_code(account, code)
        evm.storage.set_balance(account, balance)

    execute_params = fixture['exec']

    message = Message(
        origin=to_canonical_address(execute_params['origin']),
        account=to_canonical_address(execute_params['address']),
        sender=to_canonical_address(execute_params['caller']),
        value=int(execute_params['value'], 16),
        data=decode_hex(execute_params['data']),
        gas=int(execute_params['gas'], 16),
        gas_price=int(execute_params['gasPrice'], 16),
    )
    result_evm, state = execute_vm(evm, message)

    assert state.logs == fixture['logs']

    expected_output = decode_hex(fixture['out'])
    assert state.output == expected_output

    expected_gas_remaining = int(fixture['gas'], 16)
    actual_gas_remaining = state.start_gas - state.gas_used + state.total_gas_refund
    assert actual_gas_remaining == expected_gas_remaining

    for account_as_hex, account_data in fixture['post'].items():
        account = to_canonical_address(account_as_hex)

        for slot_as_hex, expected_storage_value_as_hex in account_data['storage'].items():
            slot = int(slot_as_hex, 16)
            expected_storage_value = decode_hex(expected_storage_value_as_hex)
            actual_storage_value = result_evm.storage.get_storage(account, slot)

            assert actual_storage_value == expected_storage_value

        expected_nonce = int(account_data['nonce'], 16)
        expected_code = decode_hex(account_data['code'])
        expected_balance = int(account_data['balance'], 16)

        actual_nonce = result_evm.storage.get_nonce(account)
        actual_code = result_evm.storage.get_code(account)
        actual_balance = result_evm.storage.get_balance(account)

        assert actual_nonce == expected_nonce
        assert actual_code == expected_code
        assert actual_balance == expected_balance
