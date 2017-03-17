import pytest

import itertools
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
from evm.exceptions import (
    VMError,
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


VM_TEST_FIXTURE_FILENAMES = (
    'vmArithmeticTest.json',
    'vmBitwiseLogicOperationTest.json',
    'vmPushDupSwapTest.json',
)

FIXTURES_PATHS = tuple(
    (
        filename,
        os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'VMTests', filename),
    ) for filename in VM_TEST_FIXTURE_FILENAMES
)


RAW_FIXTURES = tuple(
    (
        fixture_filename,
        json.load(open(fixture_path))
    ) for fixture_filename, fixture_path in FIXTURES_PATHS
)


SUCCESS_FIXTURES = tuple(
    (
        "{0}:{1}".format(fixture_filename, key),
        fixtures[key],
    )
    for fixture_filename, fixtures in RAW_FIXTURES
    for key in sorted(fixtures.keys())
    if 'post' in fixtures[key]
)


FAILURE_FIXTURES = tuple(
    (
        "{0}:{1}".format(fixture_filename, key),
        fixtures[key],
    )
    for fixture_filename, fixtures in RAW_FIXTURES
    for key in sorted(fixtures.keys())
    if 'post' not in fixtures[key]
)


def setup_storage(fixture, storage):
    for account_as_hex, account_data in fixture['pre'].items():
        account = to_canonical_address(account_as_hex)

        for slot_as_hex, value_as_hex in account_data['storage'].items():
            slot = int(slot_as_hex, 16)
            value = decode_hex(value)

            storage.set_storage(account, slot, value)

        nonce = int(account_data['nonce'], 16)
        code = decode_hex(account_data['code'])
        balance = int(account_data['balance'], 16)

        storage.set_nonce(account, nonce)
        storage.set_code(account, code)
        storage.set_balance(account, balance)
    return storage


@pytest.mark.parametrize(
    'fixture_name,fixture', SUCCESS_FIXTURES,
)
def test_vm_success_using_fixture(fixture_name, fixture):
    evm = EVM(MemoryStorage())

    assert fixture.get('callcreates', []) == []

    setup_storage(fixture, evm.storage)

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


@pytest.mark.parametrize(
    'fixture_name,fixture', FAILURE_FIXTURES,
)
def test_vm_failure_using_fixture(fixture_name, fixture):
    evm = EVM(MemoryStorage())

    assert fixture.get('callcreates', []) == []

    setup_storage(fixture, evm.storage)

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

    _, state = execute_vm(evm, message)
    assert state.error
    assert isinstance(state.error, VMError)
