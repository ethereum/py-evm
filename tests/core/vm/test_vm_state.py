import pytest

from eth.db.backends.memory import MemoryDB
from eth.exceptions import StateRootNotFound
from eth.vm.forks.frontier.state import FrontierState


@pytest.fixture
def state(chain_without_block_validation):
    return chain_without_block_validation.get_vm().state


def test_block_properties(chain_without_block_validation):
    chain = chain_without_block_validation
    vm = chain.get_vm()
    imported_blocks, _ = chain.import_block(vm.mine_block())
    block = imported_blocks[-1]

    assert vm.state.coinbase == block.header.coinbase
    assert vm.state.timestamp == block.header.timestamp
    assert vm.state.block_number == block.header.block_number
    assert vm.state.difficulty == block.header.difficulty
    assert vm.state.gas_limit == block.header.gas_limit


def test_missing_state_root():
    context = None
    state = FrontierState(MemoryDB(), context, b'\x0f' * 32)
    with pytest.raises(StateRootNotFound):
        state.apply_transaction(None)
