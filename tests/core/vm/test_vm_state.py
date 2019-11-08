import pytest

from eth_utils import ValidationError

from eth.db.backends.memory import MemoryDB
from eth.exceptions import StateRootNotFound
from eth.vm.forks.frontier.state import FrontierState

ADDRESS = b'\xaa' * 20
OTHER_ADDRESS = b'\xbb' * 20
INVALID_ADDRESS = b'aa' * 20


@pytest.fixture
def state(chain_without_block_validation):
    return chain_without_block_validation.get_vm().state


def test_block_properties(chain_without_block_validation):
    chain = chain_without_block_validation
    vm = chain.get_vm()
    block, _, _ = chain.import_block(vm.mine_block())

    assert vm.state.coinbase == block.header.coinbase
    assert vm.state.timestamp == block.header.timestamp
    assert vm.state.block_number == block.header.block_number
    assert vm.state.difficulty == block.header.difficulty
    assert vm.state.gas_limit == block.header.gas_limit


@pytest.mark.skip('State accepts a header, this test should build an invalid header')
def test_missing_state_root():
    context = None
    state = FrontierState(MemoryDB(), context, b'\x0f' * 32)
    with pytest.raises(StateRootNotFound):
        state.apply_transaction(None)


@pytest.mark.parametrize(
    'address, slot',
    (
        (INVALID_ADDRESS, 0),
        (ADDRESS, b'\0'),
        (ADDRESS, None),
    ),
)
def test_get_storage_input_validation(state, address, slot):
    with pytest.raises(ValidationError):
        state.get_storage(address, slot)


@pytest.mark.parametrize(
    'address, slot, new_value',
    (
        (INVALID_ADDRESS, 0, 0),
        (ADDRESS, b'\0', 0),
        (ADDRESS, 0, b'\0'),
        (ADDRESS, 0, None),
        (ADDRESS, None, 0),
    ),
)
def test_set_storage_input_validation(state, address, slot, new_value):
    with pytest.raises(ValidationError):
        state.set_storage(address, slot, new_value)


def test_delete_storage_input_validation(state):
    with pytest.raises(ValidationError):
        state.delete_storage(INVALID_ADDRESS)
