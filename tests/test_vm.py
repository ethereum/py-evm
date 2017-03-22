import pytest

import itertools
import json
import os

from eth_utils import (
    to_canonical_address,
    to_normalized_address,
    encode_hex,
    decode_hex,
    pad_left,
)

from evm.constants import (
    ZERO_ADDRESS,
)
from evm.storage.memory import (
    MemoryStorage,
)
from evm.exceptions import (
    VMError,
)
from evm.vm import (
    Environment,
    Message,
    Computation,
    EVM,
)

from evm.utils.numeric import (
    big_endian_to_int,
)


ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(__file__))


VM_TEST_FIXTURE_FILENAMES = (
    #'vmArithmeticTest.json',
    #'vmBitwiseLogicOperationTest.json',
    #'vmIOandFlowOperationsTest.json',
    #'vmLogTest.json',
    #'vmPushDupSwapTest.json',
    #'vmSha3Test.json',
    'vmSystemOperationsTest.json',
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


class TestEVM(EVM):
    def apply_message(self, message):
        """
        For VM tests, we don't actually apply messages.
        """
        computation = Computation(
            evm=self,
            message=message,
        )
        return computation

    def apply_create_message(self, message):
        """
        For VM tests, we don't actually apply messages.
        """
        computation = Computation(
            evm=self,
            message=message,
        )
        return computation


def setup_storage(fixture, storage):
    for account_as_hex, account_data in fixture['pre'].items():
        account = to_canonical_address(account_as_hex)

        for slot_as_hex, value_as_hex in account_data['storage'].items():
            slot = int(slot_as_hex, 16)
            value = decode_hex(value_as_hex)

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
    environment = Environment(
        coinbase=decode_hex(fixture['env']['currentCoinbase']),
        difficulty=int(fixture['env']['currentDifficulty'], 16),
        block_number=int(fixture['env']['currentNumber'], 16),
        gas_limit=int(fixture['env']['currentGasLimit'], 16),
        timestamp=int(fixture['env']['currentTimestamp'], 16),
    )
    evm = TestEVM(
        storage=MemoryStorage(),
        environment=environment,
    )

    setup_storage(fixture, evm.storage)

    execute_params = fixture['exec']

    message = Message(
        origin=ZERO_ADDRESS,
        to=to_canonical_address(execute_params['address']),
        sender=to_canonical_address(execute_params['caller']),
        value=int(execute_params['value'], 16),
        data=decode_hex(execute_params['data']),
        gas=int(execute_params['gas'], 16),
        gas_price=int(execute_params['gasPrice'], 16),
    )
    computation = evm.apply_computation(message)

    assert computation.error is None

    expected_logs = [
        {
            'address': to_normalized_address(log_entry[0]),
            'topics': [encode_hex(topic) for topic in log_entry[1]],
            'data': encode_hex(log_entry[2]),
        }
        for log_entry in computation.logs
    ]
    expected_logs == fixture['logs']

    expected_output = decode_hex(fixture['out'])
    assert computation.output == expected_output

    gas_meter = computation.gas_meter

    expected_gas_remaining = int(fixture['gas'], 16)
    actual_gas_remaining = gas_meter.gas_remaining
    gas_delta = actual_gas_remaining - expected_gas_remaining
    assert gas_delta == 0, "Gas difference: {0}".format(gas_delta)

    call_creates = fixture.get('callcreates', [])
    assert len(computation.children) == len(call_creates)

    for child_computation, created_call in zip(computation.children, fixture.get('callcreates', [])):
        if created_call['destination']:
            to_address = to_canonical_address(created_call['destination'])
        else:
            to_address = ZERO_ADDRESS
        data = decode_hex(created_call['data'])
        gas_limit = int(created_call['gasLimit'], 16)
        value = int(created_call['value'], 16)

        assert child_computation.msg.to == to_address
        assert data == child_computation.msg.data
        assert gas_limit == child_computation.msg.gas
        assert value == child_computation.msg.value

    for account_as_hex, account_data in fixture['post'].items():
        account = to_canonical_address(account_as_hex)

        for slot_as_hex, expected_storage_value_as_hex in account_data['storage'].items():
            slot = int(slot_as_hex, 16)
            expected_storage_value = pad_left(
                decode_hex(expected_storage_value_as_hex),
                32,
                b'\x00',
            )
            actual_storage_value = pad_left(
                evm.storage.get_storage(account, slot),
                32,
                b'\x00',
            )

            assert actual_storage_value == expected_storage_value

        expected_nonce = int(account_data['nonce'], 16)
        expected_code = decode_hex(account_data['code'])
        expected_balance = int(account_data['balance'], 16)

        actual_nonce = evm.storage.get_nonce(account)
        actual_code = evm.storage.get_code(account)
        actual_balance = evm.storage.get_balance(account)

        assert actual_nonce == expected_nonce
        assert actual_code == expected_code
        assert actual_balance == expected_balance


@pytest.mark.parametrize(
    'fixture_name,fixture', FAILURE_FIXTURES,
)
def test_vm_failure_using_fixture(fixture_name, fixture):
    environment = Environment(
        block_number=int(fixture['env']['currentNumber'], 16),
        gas_limit=int(fixture['env']['currentGasLimit'], 16),
        timestamp=int(fixture['env']['currentTimestamp'], 16),
    )
    evm = TestEVM(
        storage=MemoryStorage(),
        environment=environment,
    )

    assert fixture.get('callcreates', []) == []

    setup_storage(fixture, evm.storage)

    execute_params = fixture['exec']

    message = Message(
        origin=to_canonical_address(execute_params['origin']),
        to=to_canonical_address(execute_params['address']),
        sender=to_canonical_address(execute_params['caller']),
        value=int(execute_params['value'], 16),
        data=decode_hex(execute_params['data']),
        gas=int(execute_params['gas'], 16),
        gas_price=int(execute_params['gasPrice'], 16),
    )

    computation = evm.apply_computation(message)
    assert computation.error
    assert isinstance(computation.error, VMError)
