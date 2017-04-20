import pytest

import json
import os

from trie.db.memory import (
    MemoryDB,
)

from eth_utils import (
    keccak,
)

from evm.exceptions import (
    VMError,
)
from evm.rlp.headers import (
    BlockHeader,
)
from evm.vm.evm import (
    MetaEVM,
)
from evm.vm.flavors import (
    FrontierEVM,
    HomesteadEVM,
)
from evm.vm.flavors.mainnet import (
    FRONTIER_BLOCK_RANGE,
    HOMESTEAD_BLOCK_RANGE,
)
from evm.vm import (
    Message,
    Computation,
)

from evm.utils.fixture_tests import (
    normalize_vmtest_fixture,
    recursive_find_files,
    setup_state_db,
)


ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(__file__))


BASE_FIXTURE_PATH = os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'VMTests')


FIXTURES_PATHS = tuple(recursive_find_files(BASE_FIXTURE_PATH, "*.json"))


RAW_FIXTURES = tuple(
    (
        os.path.relpath(fixture_path, BASE_FIXTURE_PATH),
        json.load(open(fixture_path)),
    )
    for fixture_path in FIXTURES_PATHS
    if (
        "Performance" not in fixture_path and
        "Limits" not in fixture_path
    )
)


FIXTURES = tuple(
    (
        "{0}:{1}".format(fixture_filename, key),
        normalize_vmtest_fixture(fixtures[key]),
    )
    for fixture_filename, fixtures in RAW_FIXTURES
    for key in sorted(fixtures.keys())
)


#
# Testing Overrides
#
def apply_message_for_testing(self, message):
    """
    For VM tests, we don't actually apply messages.
    """
    computation = Computation(
        evm=self,
        message=message,
    )
    return computation


def apply_create_message_for_testing(self, message):
    """
    For VM tests, we don't actually apply messages.
    """
    computation = Computation(
        evm=self,
        message=message,
    )
    return computation


def get_block_hash_for_testing(self, block_number):
    if block_number >= self.block.header.block_number:
        return b''
    elif block_number < self.block.header.block_number - 256:
        return b''
    else:
        return keccak("{0}".format(block_number))


FrontierEVMForTesting = FrontierEVM.configure(
    name='FrontierEVMForTesting',
    apply_message=apply_create_message_for_testing,
    apply_create_message=apply_create_message_for_testing,
    get_block_hash=get_block_hash_for_testing,
)
HomesteadEVMForTesting = HomesteadEVM.configure(
    name='HomesteadEVMForTesting',
    apply_message=apply_create_message_for_testing,
    apply_create_message=apply_create_message_for_testing,
    get_block_hash=get_block_hash_for_testing,
)
EVMForTesting = MetaEVM.configure(
    name='EVMForTesting',
    evm_block_ranges=(
        (FRONTIER_BLOCK_RANGE, FrontierEVMForTesting),
        (HOMESTEAD_BLOCK_RANGE, HomesteadEVMForTesting),
    ),
)


@pytest.mark.parametrize(
    'fixture_name,fixture', FIXTURES,
)
def test_vm_success_using_fixture(fixture_name, fixture):
    db = MemoryDB()
    meta_evm = EVMForTesting(db=db)
    header = BlockHeader(
        coinbase=fixture['env']['currentCoinbase'],
        difficulty=fixture['env']['currentDifficulty'],
        block_number=fixture['env']['currentNumber'],
        gas_limit=fixture['env']['currentGasLimit'],
        timestamp=fixture['env']['currentTimestamp'],
    )
    evm = meta_evm(header)
    setup_state_db(fixture['pre'], evm.block.state_db)

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

    if 'post' in fixture:
        #
        # Success checks
        #
        assert computation.error is None

        expected_logs = [
            {
                'address': log_entry[0],
                'topics': log_entry[1],
                'data': log_entry[2],
            }
            for log_entry in computation.get_log_entries()
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
        post_state = fixture['post']
    else:
        #
        # Error checks
        #
        assert computation.error
        assert isinstance(computation.error, VMError)
        post_state = fixture['pre']

    for account, account_data in post_state.items():
        for slot, expected_storage_value in account_data['storage'].items():
            actual_storage_value = evm.block.state_db.get_storage(account, slot)

            assert actual_storage_value == expected_storage_value

        expected_nonce = account_data['nonce']
        expected_code = account_data['code']
        expected_balance = account_data['balance']

        actual_nonce = evm.block.state_db.get_nonce(account)
        actual_code = evm.block.state_db.get_code(account)
        actual_balance = evm.block.state_db.get_balance(account)

        assert actual_nonce == expected_nonce
        assert actual_code == expected_code
        assert actual_balance == expected_balance
