import pytest

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
    find_fixtures,
    setup_state_db,
)


ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


BASE_FIXTURE_PATH = os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'VMTests')


def vm_fixture_skip_fn(fixture_path):
    return (
        "Performance" in fixture_path or
        "Limits" in fixture_path
    )


FIXTURES = find_fixtures(
    BASE_FIXTURE_PATH,
    normalize_vmtest_fixture,
    vm_fixture_skip_fn,
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
def test_vm_fixtures(fixture_name, fixture):
    db = MemoryDB()
    header = BlockHeader(
        coinbase=fixture['env']['currentCoinbase'],
        difficulty=fixture['env']['currentDifficulty'],
        block_number=fixture['env']['currentNumber'],
        gas_limit=fixture['env']['currentGasLimit'],
        timestamp=fixture['env']['currentTimestamp'],
    )
    meta_evm = EVMForTesting.configure(db=db)(header=header)
    evm = meta_evm.get_evm()
    setup_state_db(fixture['pre'], evm.state_db)

    message = Message(
        origin=fixture['exec']['origin'],
        to=fixture['exec']['address'],
        sender=fixture['exec']['caller'],
        value=fixture['exec']['value'],
        data=fixture['exec']['data'],
        code=evm.state_db.get_code(fixture['exec']['address']),
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
            assert data == child_computation.msg.data or child_computation.msg.code
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
            actual_storage_value = evm.state_db.get_storage(account, slot)

            assert actual_storage_value == expected_storage_value

        expected_nonce = account_data['nonce']
        expected_code = account_data['code']
        expected_balance = account_data['balance']

        actual_nonce = evm.state_db.get_nonce(account)
        actual_code = evm.state_db.get_code(account)
        actual_balance = evm.state_db.get_balance(account)

        assert actual_nonce == expected_nonce
        assert actual_code == expected_code
        assert actual_balance == expected_balance
