import pytest


@pytest.fixture
def state(chain_without_block_validation):
    return chain_without_block_validation.get_vm().state


def test_block_properties(chain_without_block_validation):
    chain = chain_without_block_validation
    vm = chain.get_vm()
    block = chain.import_block(vm.mine_block())

    assert vm.state.coinbase == block.header.coinbase
    assert vm.state.timestamp == block.header.timestamp
    assert vm.state.block_number == block.header.block_number
    assert vm.state.difficulty == block.header.difficulty
    assert vm.state.gas_limit == block.header.gas_limit
