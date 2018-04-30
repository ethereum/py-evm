import pytest

from eth_utils import decode_hex

from evm import constants

from tests.core.helpers import (
    new_transaction,
)


@pytest.fixture
def chain(chain_without_block_validation):
    return chain_without_block_validation


def test_apply_transaction(
        chain,
        funded_address,
        funded_address_private_key,
        funded_address_initial_balance):
    vm = chain.get_vm()
    tx_idx = len(vm.block.transactions)
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    from_ = funded_address
    tx = new_transaction(vm, from_, recipient, amount, funded_address_private_key)
    *_, computation = vm.apply_transaction(tx)

    assert not computation.is_error
    tx_gas = tx.gas_price * constants.GAS_TX
    account_db = vm.state.account_db
    assert account_db.get_balance(from_) == (
        funded_address_initial_balance - amount - tx_gas)
    assert account_db.get_balance(recipient) == amount
    block = vm.block
    assert block.transactions[tx_idx] == tx
    assert block.header.gas_used == constants.GAS_TX


def test_mine_block_issues_block_reward(chain):
    block = chain.mine_block()
    vm = chain.get_vm()
    coinbase_balance = vm.state.account_db.get_balance(block.header.coinbase)
    assert coinbase_balance == constants.BLOCK_REWARD


def test_import_block(chain, funded_address, funded_address_private_key):
    vm = chain.get_vm()
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    from_ = funded_address
    tx = new_transaction(vm, from_, recipient, amount, funded_address_private_key)
    *_, computation = vm.apply_transaction(tx)

    assert not computation.is_error
    parent_vm = chain.get_chain_at_block_parent(vm.block).get_vm()
    block = parent_vm.import_block(vm.block)
    assert block.transactions == (tx,)
