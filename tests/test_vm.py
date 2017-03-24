import pytest

import itertools
import json
import os

from eth_utils import (
    is_0x_prefixed,
    to_canonical_address,
    to_normalized_address,
    encode_hex,
    decode_hex,
    pad_left,
    keccak,
)

from evm.constants import (
    ZERO_ADDRESS,
)
from evm.storage.memory import (
    MemoryStorage,
)
from evm.validation import (
    validate_uint256,
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
    #'vmBlockInfoTest.json',
    #'vmEnvironmentalInfoTest.json',
    'vmIOandFlowOperationsTest.json',
    #'vmInputLimits.json',
    #'vmInputLimitsLight.json',
    #'vmLogTest.json',
    #'vmPerformanceTest.json',
    #'vmPushDupSwapTest.json',
    #'vmSha3Test.json',
    #'vmSystemOperationsTest.json',
    #'vmtests.json',
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


class EVMForTesting(EVM):
    #
    # Execution Overrides
    #
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

    #
    # Storage Overrides
    #
    def get_block_hash(self, block_number):
        if block_number >= self.environment.block_number:
            return b''
        elif block_number < self.environment.block_number - 256:
            return b''
        else:
            return keccak("{0}".format(block_number))


def setup_storage(fixture, storage):
    for account_as_hex, account_data in fixture['pre'].items():
        account = to_canonical_address(account_as_hex)

        for slot_as_hex, value_as_hex in account_data['storage'].items():
            slot = to_int(slot_as_hex)
            value = decode_hex(value_as_hex)

            storage.set_storage(account, slot, value)

        nonce = to_int(account_data['nonce'])
        code = decode_hex(account_data['code'])
        balance = to_int(account_data['balance'])

        storage.set_nonce(account, nonce)
        storage.set_code(account, code)
        storage.set_balance(account, balance)
    return storage


ORIGIN = b'\x00' * 31 + b'\x01'


def to_int(value):
    if is_0x_prefixed(value):
        if len(value) == 2:
            return 0
        else:
            return int(value, 16)
    else:
        return int(value)


@pytest.mark.parametrize(
    'fixture_name,fixture', SUCCESS_FIXTURES,
)
def test_vm_success_using_fixture(fixture_name, fixture):
    environment = Environment(
        coinbase=decode_hex(fixture['env']['currentCoinbase']),
        difficulty=to_int(fixture['env']['currentDifficulty']),
        block_number=to_int(fixture['env']['currentNumber']),
        gas_limit=to_int(fixture['env']['currentGasLimit']),
        timestamp=to_int(fixture['env']['currentTimestamp']),
    )
    evm = EVMForTesting(
        storage=MemoryStorage(),
        environment=environment,
    )

    setup_storage(fixture, evm.storage)

    execute_params = fixture['exec']

    message = Message(
        origin=to_canonical_address(execute_params['origin']),
        to=to_canonical_address(execute_params['address']),
        sender=to_canonical_address(execute_params['caller']),
        value=to_int(execute_params['value']),
        data=decode_hex(execute_params['data']),
        gas=to_int(execute_params['gas']),
        gas_price=to_int(execute_params['gasPrice']),
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

    expected_gas_remaining = to_int(fixture['gas'])
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
        gas_limit = to_int(created_call['gasLimit'])
        value = to_int(created_call['value'])

        assert child_computation.msg.to == to_address
        assert data == child_computation.msg.data
        assert gas_limit == child_computation.msg.gas
        assert value == child_computation.msg.value

    for account_as_hex, account_data in fixture['post'].items():
        account = to_canonical_address(account_as_hex)

        for slot_as_hex, expected_storage_value_as_hex in account_data['storage'].items():
            slot = to_int(slot_as_hex)
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

        expected_nonce = to_int(account_data['nonce'])
        expected_code = decode_hex(account_data['code'])
        expected_balance = to_int(account_data['balance'])

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
        coinbase=decode_hex(fixture['env']['currentCoinbase']),
        difficulty=to_int(fixture['env']['currentDifficulty']),
        block_number=to_int(fixture['env']['currentNumber']),
        gas_limit=to_int(fixture['env']['currentGasLimit']),
        timestamp=to_int(fixture['env']['currentTimestamp']),
    )
    evm = EVMForTesting(
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
        value=to_int(execute_params['value']),
        data=decode_hex(execute_params['data']),
        gas=to_int(execute_params['gas']),
        gas_price=to_int(execute_params['gasPrice']),
    )

    computation = evm.apply_computation(message)
    assert computation.error
    assert isinstance(computation.error, VMError)
