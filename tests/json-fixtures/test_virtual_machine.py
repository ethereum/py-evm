import os

from eth_hash.auto import (
    keccak,
)
from eth_utils import (
    to_bytes,
)
import pytest

from eth.consensus import (
    ConsensusContext,
)
from eth.db import (
    get_db_backend,
)
from eth.db.chain import (
    ChainDB,
)
from eth.exceptions import (
    VMError,
)
from eth.rlp.headers import (
    BlockHeader,
)
from eth.tools._utils.hashing import (
    hash_log_entries,
)
from eth.tools._utils.normalization import (
    normalize_vmtest_fixture,
)
from eth.tools.fixtures import (
    filter_fixtures,
    generate_fixture_tests,
    load_fixture,
    setup_state,
    verify_state,
)
from eth.vm.chain_context import (
    ChainContext,
)
from eth.vm.forks import (
    HomesteadVM,
)
from eth.vm.forks.homestead.computation import (
    HomesteadComputation,
)
from eth.vm.forks.homestead.state import (
    HomesteadState,
)
from eth.vm.message import (
    Message,
)
from eth.vm.transaction_context import (
    BaseTransactionContext,
)

ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

BASE_FIXTURE_PATH = os.path.join(
    ROOT_PROJECT_DIR,
    "fixtures",
    "LegacyTests",
    "Constantinople",
    "VMTests",
)


def vm_fixture_mark_fn(fixture_path, fixture_name):
    if fixture_path.startswith("vmPerformance"):
        return pytest.mark.skip("Performance tests are really slow")
    elif fixture_path == "vmSystemOperations/createNameRegistrator.json":
        return pytest.mark.skip(
            "Skipped in go-ethereum due to failure without parallel processing"
        )


def pytest_generate_tests(metafunc):
    generate_fixture_tests(
        metafunc=metafunc,
        base_fixture_path=BASE_FIXTURE_PATH,
        filter_fn=filter_fixtures(
            fixtures_base_dir=BASE_FIXTURE_PATH,
            mark_fn=vm_fixture_mark_fn,
        ),
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
def apply_message_for_testing(cls, *args):
    """
    For VM tests, we don't actually apply messages.
    """
    return cls(*args)


def apply_create_message_for_testing(cls, *args):
    """
    For VM tests, we don't actually apply messages.
    """
    return cls(*args)


def get_block_hash_for_testing(self, block_number):
    if block_number >= self.block_number:
        return b""
    elif block_number < self.block_number - 256:
        return b""
    else:
        return keccak(to_bytes(text=f"{block_number}"))


HomesteadComputationForTesting = HomesteadComputation.configure(
    __name__="HomesteadComputationForTesting",
    apply_message=apply_message_for_testing,
    apply_create_message=apply_create_message_for_testing,
)
HomesteadStateForTesting = HomesteadState.configure(
    __name__="HomesteadStateForTesting",
    get_ancestor_hash=get_block_hash_for_testing,
    computation_class=HomesteadComputationForTesting,
)
HomesteadVMForTesting = HomesteadVM.configure(
    __name__="HomesteadVMForTesting",
    _state_class=HomesteadStateForTesting,
)


@pytest.fixture(params=["Frontier", "Homestead", "EIP150", "SpuriousDragon"])
def vm_class(request):
    if request.param == "Frontier":
        pytest.skip("Only the Homestead VM rules are currently supported")
    elif request.param == "Homestead":
        return HomesteadVMForTesting
    elif request.param == "EIP150":
        pytest.skip("Only the Homestead VM rules are currently supported")
    elif request.param == "SpuriousDragon":
        pytest.skip("Only the Homestead VM rules are currently supported")
    else:
        raise AssertionError(f"Unsupported VM: {request.param}")


def fixture_to_computation(fixture, code, vm):
    message = Message(
        to=fixture["exec"]["address"],
        sender=fixture["exec"]["caller"],
        value=fixture["exec"]["value"],
        data=fixture["exec"]["data"],
        code=code,
        gas=fixture["exec"]["gas"],
    )
    transaction_context = BaseTransactionContext(
        origin=fixture["exec"]["origin"],
        gas_price=fixture["exec"]["gasPrice"],
    )
    return vm.state.get_computation(message, transaction_context).apply_computation(
        vm.state,
        message,
        transaction_context,
    )


def fixture_to_bytecode_computation(fixture, code, vm):
    return vm.execute_bytecode(
        origin=fixture["exec"]["origin"],
        gas_price=fixture["exec"]["gasPrice"],
        gas=fixture["exec"]["gas"],
        to=fixture["exec"]["address"],
        sender=fixture["exec"]["caller"],
        value=fixture["exec"]["value"],
        data=fixture["exec"]["data"],
        code=code,
    )


@pytest.mark.parametrize(
    "computation_getter",
    (
        fixture_to_bytecode_computation,
        fixture_to_computation,
    ),
)
def test_vm_fixtures(fixture, vm_class, computation_getter):
    db = get_db_backend()
    chaindb = ChainDB(db)
    consensus_context = ConsensusContext(db)
    header = BlockHeader(
        coinbase=fixture["env"]["currentCoinbase"],
        difficulty=fixture["env"]["currentDifficulty"],
        block_number=fixture["env"]["currentNumber"],
        gas_limit=fixture["env"]["currentGasLimit"],
        timestamp=fixture["env"]["currentTimestamp"],
    )

    # None of the VM tests (currently) test chain ID, so the setting doesn't matter
    # here. When they *do* start testing ID, they will have to supply it as part of
    # the environment. For now, just hard-code it to something not used in practice:
    chain_context = ChainContext(chain_id=0)

    vm = vm_class(
        header=header,
        chaindb=chaindb,
        chain_context=chain_context,
        consensus_context=consensus_context,
    )
    state = vm.state
    setup_state(fixture["pre"], state)
    code = state.get_code(fixture["exec"]["address"])
    # Update state_root manually
    vm._block = vm.get_block().copy(
        header=vm.get_header().copy(state_root=state.state_root)
    )

    message = Message(
        to=fixture["exec"]["address"],
        sender=fixture["exec"]["caller"],
        value=fixture["exec"]["value"],
        data=fixture["exec"]["data"],
        code=code,
        gas=fixture["exec"]["gas"],
    )
    transaction_context = BaseTransactionContext(
        origin=fixture["exec"]["origin"],
        gas_price=fixture["exec"]["gasPrice"],
    )
    computation = vm.state.get_computation(
        message, transaction_context
    ).apply_computation(
        vm.state,
        message,
        transaction_context,
    )
    # Update state_root manually
    vm._block = vm.get_block().copy(
        header=vm.get_header().copy(state_root=computation.state.state_root),
    )

    if "post" in fixture:
        #
        # Success checks
        #
        assert not computation.is_error

        log_entries = computation.get_log_entries()
        if "logs" in fixture:
            actual_logs_hash = hash_log_entries(log_entries)
            expected_logs_hash = fixture["logs"]
            assert expected_logs_hash == actual_logs_hash
        elif log_entries:
            raise AssertionError(f"Got log entries: {log_entries}")

        expected_output = fixture["out"]
        assert computation.output == expected_output

        gas_meter = computation._gas_meter

        expected_gas_remaining = fixture["gas"]
        actual_gas_remaining = gas_meter.gas_remaining
        gas_delta = actual_gas_remaining - expected_gas_remaining
        assert gas_delta == 0, f"Gas difference: {gas_delta}"

        call_creates = fixture.get("callcreates", [])
        assert len(computation.children) == len(call_creates)

        call_creates = fixture.get("callcreates", [])
        for child_computation, created_call in zip(computation.children, call_creates):
            to_address = created_call["destination"]
            data = created_call["data"]
            gas_limit = created_call["gasLimit"]
            value = created_call["value"]

            assert child_computation.msg.to == to_address
            assert data == child_computation.msg.data or child_computation.msg.code
            assert gas_limit == child_computation.msg.gas
            assert value == child_computation.msg.value
        expected_account_db = fixture["post"]
    else:
        #
        # Error checks
        #
        assert computation.is_error
        assert isinstance(computation._error, VMError)
        expected_account_db = fixture["pre"]

    verify_state(expected_account_db, vm.state)
