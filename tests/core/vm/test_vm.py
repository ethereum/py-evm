import pytest

from eth_utils import decode_hex

from eth import constants
from eth.chains.base import (
    MiningChain,
)
from eth.tools.factories.transaction import (
    new_transaction
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
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    from_ = funded_address
    tx = new_transaction(vm, from_, recipient, amount, funded_address_private_key)
    receipt, computation = vm.apply_transaction(vm.get_header(), tx)
    new_header = vm.add_receipt_to_header(vm.get_header(), receipt)

    assert not computation.is_error
    tx_gas = tx.gas_price * constants.GAS_TX
    state = vm.state
    assert state.get_balance(from_) == (
        funded_address_initial_balance - amount - tx_gas)
    assert state.get_balance(recipient) == amount

    assert new_header.gas_used == constants.GAS_TX


def test_mine_block_issues_block_reward(chain):
    if not isinstance(chain, MiningChain):
        pytest.skip("Only test mining on a MiningChain")
        return

    block = chain.mine_block()
    vm = chain.get_vm()
    coinbase_balance = vm.state.get_balance(block.header.coinbase)
    assert coinbase_balance == vm.get_block_reward()


def test_import_block(chain, funded_address, funded_address_private_key):
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    from_ = funded_address
    tx = new_transaction(chain.get_vm(), from_, recipient, amount, funded_address_private_key)
    if isinstance(chain, MiningChain):
        # Can use the mining chain functionality to build transactions in-flight
        pending_header = chain.header
        new_block, _, computation = chain.apply_transaction(tx)
    else:
        # Have to manually build the block for the import_block test
        new_block, _, computations = chain.build_block_with_transactions([tx])
        computation = computations[0]

        # Generate the pending header to import the new block on
        pending_header = chain.create_header_from_parent(chain.get_canonical_head())

    assert not computation.is_error

    # import the built block
    validation_vm = chain.get_vm(pending_header)
    block = validation_vm.import_block(new_block)
    assert block.transactions == (tx, )
