import pytest

from eth_utils import decode_hex

from evm import constants

from tests.core.fixtures import chain_without_block_validation  # noqa: F401
from tests.core.helpers import new_transaction


def test_apply_transaction(chain_without_block_validation):  # noqa: F811
    chain = chain_without_block_validation  # noqa: F811
    vm = chain.get_vm()
    tx_idx = len(vm.block.transactions)
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    from_ = chain.funded_address
    tx = new_transaction(vm, from_, recipient, amount, chain.funded_address_private_key)
    computation = vm.apply_transaction(tx)
    assert computation.error is None
    tx_gas = tx.gas_price * constants.GAS_TX
    with vm.state_db(read_only=True) as state_db:
        assert state_db.get_balance(from_) == (
            chain.funded_address_initial_balance - amount - tx_gas)
        assert state_db.get_balance(recipient) == amount
    block = vm.block
    assert block.transactions[tx_idx] == tx
    assert block.header.gas_used == constants.GAS_TX


def test_mine_block(chain_without_block_validation):  # noqa: F811
    chain = chain_without_block_validation  # noqa: F811
    vm = chain.get_vm()
    block = vm.mine_block()
    with vm.state_db(read_only=True) as state_db:
        assert state_db.get_balance(block.header.coinbase) == constants.BLOCK_REWARD


def test_import_block(chain_without_block_validation):  # noqa: F811
    chain = chain_without_block_validation  # noqa: F811
    vm = chain.get_vm()
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    from_ = chain.funded_address
    tx = new_transaction(vm, from_, recipient, amount, chain.funded_address_private_key)
    computation = vm.apply_transaction(tx)
    assert computation.error is None
    parent_vm = chain.get_chain_at_block_parent(vm.block).get_vm()
    block = parent_vm.import_block(vm.block)
    assert block.transactions == [tx]


def test_state_db(chain_without_block_validation):  # noqa: F811
    vm = chain_without_block_validation.get_vm()
    address = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    initial_state_root = vm.block.header.state_root

    # test cannot write to state_db after context exits
    with vm.state_db() as state_db:
        pass

    with pytest.raises(Exception):  # TODO: fix this to be a real exception
        state_db.increment_nonce(address)

    with vm.state_db(read_only=True) as state_db:
        state_db.get_balance(address)
    assert vm.block.header.state_root == initial_state_root

    with vm.state_db() as state_db:
        state_db.set_balance(address, 10)
    assert vm.block.header.state_root != initial_state_root

    with vm.state_db(read_only=True) as state_db:
        with pytest.raises(TypeError):
            state_db.set_balance(address, 0)
