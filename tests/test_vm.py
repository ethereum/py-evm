import pytest

import json
import os

from eth_utils import (
    is_0x_prefixed,
    to_canonical_address,
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
from evm.exceptions import (
    VMError,
)
from evm.vm import (
    Environment,
    Message,
    Computation,
    EVM,
)
from evm.preconfigured.genesis import (
    GENESIS_OPCODES,
)


def to_int(value):
    if is_0x_prefixed(value):
        if len(value) == 2:
            return 0
        else:
            return int(value, 16)
    else:
        return int(value)


def normalize_fixture(fixture):
    normalized_fixture = {
        'env': {
            'currentCoinbase': decode_hex(fixture['env']['currentCoinbase']),
            'currentDifficulty': to_int(fixture['env']['currentDifficulty']),
            'currentNumber': to_int(fixture['env']['currentNumber']),
            'currentGasLimit': to_int(fixture['env']['currentGasLimit']),
            'currentTimestamp': to_int(fixture['env']['currentTimestamp']),
        },
        'exec': {
            'origin': to_canonical_address(fixture['exec']['origin']),
            'address': to_canonical_address(fixture['exec']['address']),
            'caller': to_canonical_address(fixture['exec']['caller']),
            'value': to_int(fixture['exec']['value']),
            'data': decode_hex(fixture['exec']['data']),
            'gas': to_int(fixture['exec']['gas']),
            'gasPrice': to_int(fixture['exec']['gasPrice']),
        },
        'pre': {
            to_canonical_address(address): {
                'balance': to_int(state['balance']),
                'code': decode_hex(state['code']),
                'nonce': to_int(state['nonce']),
                'storage': {
                    to_int(slot): decode_hex(value)
                    for slot, value in state['storage'].items()
                },
            } for address, state in fixture['pre'].items()
        },
    }

    if 'post' in fixture:
        normalized_fixture['post'] = {
            to_canonical_address(address): {
                'balance': to_int(state['balance']),
                'code': decode_hex(state['code']),
                'nonce': to_int(state['nonce']),
                'storage': {
                    to_int(slot): decode_hex(value)
                    for slot, value in state['storage'].items()
                },
            } for address, state in fixture['post'].items()
        }

    if 'callcreates' in fixture:
        normalized_fixture['callcreates'] = [
            {
                'data': decode_hex(created_call['data']),
                'destination': (
                    to_canonical_address(created_call['destination'])
                    if created_call['destination']
                    else ZERO_ADDRESS
                ),
                'gasLimit': to_int(created_call['gasLimit']),
                'value': to_int(created_call['value']),
            } for created_call in fixture['callcreates']
        ]

    if 'gas' in fixture:
        normalized_fixture['gas'] = to_int(fixture['gas'])

    if 'out' in fixture:
        normalized_fixture['out'] = decode_hex(fixture['out'])

    if 'logs' in fixture:
        normalized_fixture['logs'] = [
            {
                'address': to_canonical_address(log_entry['address']),
                'topics': [decode_hex(topic) for topic in log_entry['topics']],
                'data': decode_hex(log_entry['data']),
                # 'bloom': decode_hex(log_entry['bloom']),  #TODO
            } for log_entry in fixture['logs']
        ]

    return normalized_fixture


GenesisEVM = EVM.create(name='genesis', opcode_classes=GENESIS_OPCODES)


ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(__file__))


VM_TEST_FIXTURE_FILENAMES = (
    'vmArithmeticTest.json',
    'vmBitwiseLogicOperationTest.json',
    'vmBlockInfoTest.json',
    'vmEnvironmentalInfoTest.json',
    'vmIOandFlowOperationsTest.json',
    'vmInputLimits.json',
    'vmInputLimitsLight.json',
    'vmLogTest.json',
    'vmPerformanceTest.json',
    'vmPushDupSwapTest.json',
    'vmSha3Test.json',
    'vmSystemOperationsTest.json',
    'vmtests.json',
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
        normalize_fixture(fixtures[key]),
    )
    for fixture_filename, fixtures in RAW_FIXTURES
    for key in sorted(fixtures.keys())
    if 'post' in fixtures[key]
)


FAILURE_FIXTURES = tuple(
    (
        "{0}:{1}".format(fixture_filename, key),
        normalize_fixture(fixtures[key]),
    )
    for fixture_filename, fixtures in RAW_FIXTURES
    for key in sorted(fixtures.keys())
    if 'post' not in fixtures[key]
)


class EVMForTesting(GenesisEVM):
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
    for account, account_data in fixture['pre'].items():
        for slot, value in account_data['storage'].items():
            storage.set_storage(account, slot, value)

        nonce = account_data['nonce']
        code = account_data['code']
        balance = account_data['balance']

        storage.set_nonce(account, nonce)
        storage.set_code(account, code)
        storage.set_balance(account, balance)
    return storage


ORIGIN = b'\x00' * 31 + b'\x01'


@pytest.mark.parametrize(
    'fixture_name,fixture', SUCCESS_FIXTURES,
)
def test_vm_success_using_fixture(fixture_name, fixture):
    environment = Environment(
        coinbase=fixture['env']['currentCoinbase'],
        difficulty=fixture['env']['currentDifficulty'],
        block_number=fixture['env']['currentNumber'],
        gas_limit=fixture['env']['currentGasLimit'],
        timestamp=fixture['env']['currentTimestamp'],
    )
    evm = EVMForTesting(
        storage=MemoryStorage(),
        environment=environment,
    )

    setup_storage(fixture, evm.storage)

    message = Message(
        origin=fixture['exec']['origin'],
        to=fixture['exec']['address'],
        sender=fixture['exec']['caller'],
        value=fixture['exec']['value'],
        data=fixture['exec']['data'],
        gas=fixture['exec']['gas'],
        gas_price=fixture['exec']['gasPrice'],
    )
    computation = evm.apply_computation(message)

    assert computation.error is None

    expected_logs = [
        {
            'address': log_entry[0],
            'topics': log_entry[1],
            'data': log_entry[2],
        }
        for log_entry in computation.logs
    ]
    expected_logs == fixture['logs']

    expected_output = fixture['out']
    assert computation.output == expected_output

    gas_meter = computation.gas_meter

    expected_gas_remaining = fixture['gas']
    actual_gas_remaining = gas_meter.gas_remaining
    gas_delta = actual_gas_remaining - expected_gas_remaining
    assert gas_delta == 0, "Gas difference: {0}".format(gas_delta)

    call_creates = fixture.get('callcreates', [])
    assert len(computation.children) == len(call_creates)

    for child_computation, created_call in zip(computation.children, fixture.get('callcreates', [])):
        to_address = created_call['destination']
        data = created_call['data']
        gas_limit = created_call['gasLimit']
        value = created_call['value']

        assert child_computation.msg.to == to_address
        assert data == child_computation.msg.data
        assert gas_limit == child_computation.msg.gas
        assert value == child_computation.msg.value

    for account_as_hex, account_data in fixture['post'].items():
        account = to_canonical_address(account_as_hex)

        for slot, unpadded_expected_storage_value in account_data['storage'].items():
            expected_storage_value = pad_left(
                unpadded_expected_storage_value,
                32,
                b'\x00',
            )
            actual_storage_value = pad_left(
                evm.storage.get_storage(account, slot),
                32,
                b'\x00',
            )

            assert actual_storage_value == expected_storage_value

        expected_nonce = account_data['nonce']
        expected_code = account_data['code']
        expected_balance = account_data['balance']

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
        coinbase=fixture['env']['currentCoinbase'],
        difficulty=fixture['env']['currentDifficulty'],
        block_number=fixture['env']['currentNumber'],
        gas_limit=fixture['env']['currentGasLimit'],
        timestamp=fixture['env']['currentTimestamp'],
    )
    evm = EVMForTesting(
        storage=MemoryStorage(),
        environment=environment,
    )

    assert fixture.get('callcreates', []) == []

    setup_storage(fixture, evm.storage)

    message = Message(
        origin=fixture['exec']['origin'],
        to=fixture['exec']['address'],
        sender=fixture['exec']['caller'],
        value=fixture['exec']['value'],
        data=fixture['exec']['data'],
        gas=fixture['exec']['gas'],
        gas_price=fixture['exec']['gasPrice'],
    )

    computation = evm.apply_computation(message)
    assert computation.error
    assert isinstance(computation.error, VMError)
