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
    computation, _ = vm.apply_transaction(tx)
    access_logs = computation.vm_state.access_logs

    assert not computation.is_error
    tx_gas = tx.gas_price * constants.GAS_TX
    with vm.state.state_db(read_only=True) as state_db:
        assert state_db.get_balance(from_) == (
            chain.funded_address_initial_balance - amount - tx_gas)
        assert state_db.get_balance(recipient) == amount
    block = vm.block
    assert block.transactions[tx_idx] == tx
    assert block.header.gas_used == constants.GAS_TX

    assert len(access_logs.reads) > 0
    assert len(access_logs.writes) > 0
    # TODO: Add more tests for accesss_logs


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
    computation, _ = vm.apply_transaction(tx)

    assert not computation.is_error
    parent_vm = chain.get_chain_at_block_parent(vm.block).get_vm()
    block = parent_vm.import_block(vm.block)
    assert block.transactions == [tx]


def test_get_cumulative_gas_used(chain_without_block_validation):  # noqa: F811
    chain = chain_without_block_validation  # noqa: F811
    vm = chain.get_vm()

    # Empty block.
    block = vm.mine_block()
    chain.import_block(block)
    block1 = chain.get_canonical_block_by_number(1)

    blockgas = vm.get_cumulative_gas_used(block1)

    assert blockgas == 0

    # Only one transaction in the block.
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    vm = chain.get_vm()
    from_ = chain.funded_address
    tx = new_transaction(vm, from_, recipient, amount, chain.funded_address_private_key)

    vm.apply_transaction(tx)
    block = vm.mine_block()
    chain.import_block(block)
    block2 = chain.get_canonical_block_by_number(2)

    blockgas = vm.get_cumulative_gas_used(block2)

    assert blockgas == constants.GAS_TX
