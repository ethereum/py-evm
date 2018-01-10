from eth_utils import decode_hex

from evm import constants
from evm.utils.address import generate_create2_contract_address

from tests.core.fixtures import (  # noqa: F401
    chain_without_block_validation,
    shard_chain_without_block_validation,
)
from tests.core.helpers import (
    new_transaction,
    new_sharding_transaction,
)


def test_apply_transaction(chain_without_block_validation):  # noqa: F811
    chain = chain_without_block_validation  # noqa: F811
    vm = chain.get_vm()
    tx_idx = len(vm.block.transactions)
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    from_ = chain.funded_address
    tx = new_transaction(vm, from_, recipient, amount, chain.funded_address_private_key)
    computation = vm.apply_transaction(tx)
    assert not computation.is_error
    tx_gas = tx.gas_price * constants.GAS_TX
    with vm.state.state_db(read_only=True) as state_db:
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
    with vm.state.state_db(read_only=True) as state_db:
        assert state_db.get_balance(block.header.coinbase) == constants.BLOCK_REWARD


def test_import_block(chain_without_block_validation):  # noqa: F811
    chain = chain_without_block_validation  # noqa: F811
    vm = chain.get_vm()
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    from_ = chain.funded_address
    tx = new_transaction(vm, from_, recipient, amount, chain.funded_address_private_key)
    computation = vm.apply_transaction(tx)
    assert not computation.is_error
    parent_vm = chain.get_chain_at_block_parent(vm.block).get_vm()
    block = parent_vm.import_block(vm.block)
    assert block.transactions == [tx]


def test_sharding_transaction(shard_chain_without_block_validation):  # noqa: F811
    # Target contract, i.e. funded_address, is a simple ether transfer contract which transfer
    # specified amount of ether to recipient.
    # TODO: update contract_deployment_code
    contract_deployment_code = b''
    contract_addr = generate_create2_contract_address(b'', contract_deployment_code)

    chain = shard_chain_without_block_validation()
    deploy_tx = new_sharding_transaction(contract_addr, b'', 0, b'', b'', contract_deployment_code)

    vm = chain.get_vm()
    computation = vm.apply_transaction(deploy_tx)
    assert not computation.is_error

    # Transfer ether to recipient
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    tx_initiator = chain.funded_address
    transfer_tx = new_sharding_transaction(tx_initiator, recipient, amount, b'', b'', b'')
    computation = vm.execute_transaction(transfer_tx)
    assert not computation.is_error
    with vm.state.state_db(read_only=True) as state_db:
        assert state_db.get_balance(recipient) == amount
