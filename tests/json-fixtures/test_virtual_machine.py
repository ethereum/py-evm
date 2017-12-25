import os

import pytest

from evm.db import (
    get_db_backend,
)
from evm.db.chain import BaseChainDB

from eth_utils import (
    keccak,
)

from evm.exceptions import (
    VMError,
)
from evm.rlp.headers import (
    BlockHeader,
)
from evm.vm.forks import (
    HomesteadVM,
)
from evm.vm.forks.homestead import (
    HomesteadVMState,
)
from evm.vm import (
    Message,
    Computation,
)

from evm.utils.fixture_tests import (
    normalize_vmtest_fixture,
    generate_fixture_tests,
    load_fixture,
    filter_fixtures,
    setup_state_db,
    verify_state_db,
    hash_log_entries,
)


ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


BASE_FIXTURE_PATH = os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'VMTests')


def vm_fixture_mark_fn(fixture_path, fixture_name):
    if fixture_path.startswith('vmPerformance'):
        return pytest.mark.skip('Performance tests are really slow')
    elif fixture_path == 'vmSystemOperations/createNameRegistrator.json':
        return pytest.mark.skip(
            'Skipped in go-ethereum due to failure without parallel processing'
        )


def pytest_generate_tests(metafunc):
    generate_fixture_tests(
        metafunc=metafunc,
        base_fixture_path=BASE_FIXTURE_PATH,
        filter_fn=filter_fixtures(
            fixtures_base_dir=BASE_FIXTURE_PATH,
            mark_fn=vm_fixture_mark_fn,
        )
    )


@pytest.fixture
def fixture(fixture_data):
    fixture_path, fixture_key = fixture_data
    fixture = load_fixture(
        fixture_path,
        fixture_key,
        normalize_vmtest_fixture,
    )
    return fixture


#
# Testing Overrides
#
def apply_message_for_testing(self, message):
    """
    For VM tests, we don't actually apply messages.
    """
    computation = Computation(
        state=self,
        message=message,
    )
    print('yoo')
    return computation


def apply_create_message_for_testing(self, message):
    """
    For VM tests, we don't actually apply messages.
    """
    computation = Computation(
        state=self,
        message=message,
    )
    print('yoo')
    return computation


def get_block_hash_for_testing(self, block_number):
    if block_number >= self.block_header.block_number:
        return b''
    elif block_number < self.block_header.block_number - 256:
        return b''
    else:
        return keccak("{0}".format(block_number))


HomesteadVMStateForTesting = HomesteadVMState.configure(
    name='HomesteadVMStateForTesting',
    apply_message=apply_message_for_testing,
    apply_create_message=apply_create_message_for_testing,
    get_ancestor_hash=get_block_hash_for_testing,
)
HomesteadVMForTesting = HomesteadVM.configure(
    name='HomesteadVMForTesting',
    _state_class=HomesteadVMStateForTesting,
)


@pytest.fixture(params=['Frontier', 'Homestead', 'EIP150', 'SpuriousDragon'])
def vm_class(request):
    if request.param == 'Frontier':
        pytest.skip('Only the Homestead VM rules are currently supported')
    elif request.param == 'Homestead':
        return HomesteadVMForTesting
    elif request.param == 'EIP150':
        pytest.skip('Only the Homestead VM rules are currently supported')
    elif request.param == 'SpuriousDragon':
        pytest.skip('Only the Homestead VM rules are currently supported')
    else:
        assert False, "Unsupported VM: {0}".format(request.param)


def test_vm_fixtures(fixture, vm_class):
    chaindb = BaseChainDB(get_db_backend())
    header = BlockHeader(
        coinbase=fixture['env']['currentCoinbase'],
        difficulty=fixture['env']['currentDifficulty'],
        block_number=fixture['env']['currentNumber'],
        gas_limit=fixture['env']['currentGasLimit'],
        timestamp=fixture['env']['currentTimestamp'],
    )
    vm = vm_class(header=header, chaindb=chaindb)

    with vm.state.state_db() as state_db:
        setup_state_db(fixture['pre'], state_db)
        code = state_db.get_code(fixture['exec']['address'])

    message = Message(
        origin=fixture['exec']['origin'],
        to=fixture['exec']['address'],
        sender=fixture['exec']['caller'],
        value=fixture['exec']['value'],
        data=fixture['exec']['data'],
        code=code,
        gas=fixture['exec']['gas'],
        gas_price=fixture['exec']['gasPrice'],
    )
    computation = vm.state.apply_computation(message)

    if 'post' in fixture:
        #
        # Success checks
        #
        assert not computation.is_error

        log_entries = computation.get_log_entries()
        if 'logs' in fixture:
            actual_logs_hash = hash_log_entries(log_entries)
            expected_logs_hash = fixture['logs']
            assert expected_logs_hash == actual_logs_hash
        elif log_entries:
            raise AssertionError("Got log entries: {0}".format(log_entries))

        expected_output = fixture['out']
        assert computation.output == expected_output

        gas_meter = computation.gas_meter

        expected_gas_remaining = fixture['gas']
        actual_gas_remaining = gas_meter.gas_remaining
        gas_delta = actual_gas_remaining - expected_gas_remaining
        assert gas_delta == 0, "Gas difference: {0}".format(gas_delta)

        call_creates = fixture.get('callcreates', [])
        assert len(computation.children) == len(call_creates)

        call_creates = fixture.get('callcreates', [])
        for child_computation, created_call in zip(computation.children, call_creates):
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
        assert computation.is_error
        assert isinstance(computation._error, VMError)
        post_state = fixture['pre']

    with vm.state.state_db(read_only=True) as state_db:
        verify_state_db(post_state, state_db)
