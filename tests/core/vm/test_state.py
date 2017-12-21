from tests.core.fixtures import chain_without_block_validation  # noqa: F401


def test_state_properties(chain_without_block_validation):  # noqa: F811
    chain = chain_without_block_validation  # noqa: F811
    vm = chain.get_vm()
    block = vm.mine_block()

    assert vm.state.blockhash == block.hash
    assert vm.state.coinbase == block.header.coinbase
    assert vm.state.timestamp == block.header.timestamp
    assert vm.state.number == block.header.block_number
    assert vm.state.difficulty == block.header.difficulty
    assert vm.state.gaslimit == block.header.gas_limit
