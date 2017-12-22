import pytest

from eth_utils import (
    decode_hex,
)

from tests.core.fixtures import chain_without_block_validation  # noqa: F401


@pytest.fixture  # noqa: F811
def state(chain_without_block_validation):
    return chain_without_block_validation.get_vm().state


def test_block_properties(chain_without_block_validation):  # noqa: F811
    chain = chain_without_block_validation  # noqa: F811
    vm = chain.get_vm()
    block = vm.mine_block()

    assert vm.state.blockhash == block.hash
    assert vm.state.coinbase == block.header.coinbase
    assert vm.state.timestamp == block.header.timestamp
    assert vm.state.number == block.header.block_number
    assert vm.state.difficulty == block.header.difficulty
    assert vm.state.gaslimit == block.header.gas_limit


def test_state_db(state):  # noqa: F811
    address = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    initial_state_root = state.block_header.state_root

    # test cannot write to state_db after context exits
    with state.state_db() as state_db:
        pass

    with pytest.raises(TypeError):
        state_db.increment_nonce(address)

    with state.state_db(read_only=True) as state_db:
        state_db.get_balance(address)
    assert state.block_header.state_root == initial_state_root

    with state.state_db() as state_db:
        state_db.set_balance(address, 10)
    assert state.block_header.state_root != initial_state_root

    with state.state_db(read_only=True) as state_db:
        with pytest.raises(TypeError):
            state_db.set_balance(address, 0)
