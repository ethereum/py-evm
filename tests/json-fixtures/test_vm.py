import pytest

import os

from trie.db.memory import (
    MemoryDB,
)

from eth_utils import (
    keccak,
)

from evm import (
    EVM,
)
from evm.exceptions import (
    VMError,
)
from evm.rlp.headers import (
    BlockHeader,
)
from evm.vm.flavors import (
    FrontierVM,
    HomesteadVM,
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
    verify_state_db,
)


ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


BASE_FIXTURE_PATH = os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'VMTests')


def vm_fixture_skip_fn(fixture_path, fixture_name, fixture):
    return False


def vm_fixture_mark_fn(fixture_name):
    if 'Performance' in fixture_name:
        return pytest.mark.vm_performance
    elif 'vmInputLimits' in fixture_name:
        return pytest.mark.vm_limits
    else:
        return None


FIXTURES = find_fixtures(
    BASE_FIXTURE_PATH,
    normalize_vmtest_fixture,
    skip_fn=vm_fixture_skip_fn,
    mark_fn=vm_fixture_mark_fn,
)


#
# Testing Overrides
#
def apply_message_for_testing(self, message):
    """
    For VM tests, we don't actually apply messages.
    """
    computation = Computation(
        vm=self,
        message=message,
    )
    return computation


def apply_create_message_for_testing(self, message):
    """
    For VM tests, we don't actually apply messages.
    """
    computation = Computation(
        vm=self,
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


FrontierVMForTesting = FrontierVM.configure(
    name='FrontierVMForTesting',
    apply_message=apply_create_message_for_testing,
    apply_create_message=apply_create_message_for_testing,
    get_block_hash=get_block_hash_for_testing,
)
HomesteadVMForTesting = HomesteadVM.configure(
    name='HomesteadVMForTesting',
    apply_message=apply_create_message_for_testing,
    apply_create_message=apply_create_message_for_testing,
    get_block_hash=get_block_hash_for_testing,
)


EVMForTesting = EVM.configure(
    name='EVMForTesting',
    vm_block_ranges=(
        (FRONTIER_BLOCK_RANGE, FrontierVMForTesting),
        (HOMESTEAD_BLOCK_RANGE, HomesteadVMForTesting),
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
    evm = EVMForTesting.configure(db=db)(header=header)
    state_db = setup_state_db(fixture['pre'], evm.get_state_db())
    evm.header.state_root = state_db.root_hash

    message = Message(
        origin=fixture['exec']['origin'],
        to=fixture['exec']['address'],
        sender=fixture['exec']['caller'],
        value=fixture['exec']['value'],
        data=fixture['exec']['data'],
        code=evm.get_state_db().get_code(fixture['exec']['address']),
        gas=fixture['exec']['gas'],
        gas_price=fixture['exec']['gasPrice'],
    )
    vm = evm.get_vm()
    computation = vm.apply_computation(message)

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

    verify_state_db(post_state, vm.state_db)
