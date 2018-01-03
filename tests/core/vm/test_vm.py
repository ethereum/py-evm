import copy

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
    # TODO: Add more tests for access_logs


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


def test_create_block(chain_without_block_validation):  # noqa: F811
    chain = chain_without_block_validation  # noqa: F811
    vm = chain.get_vm()

    # (1) Empty block.
    # block = vm.mine_block()
    block0 = chain.import_block(vm.block)

    # (2) Generate tx.witness.
    # Prepare the transaction
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    from_ = chain.funded_address
    tx = new_transaction(vm, from_, recipient, amount, chain.funded_address_private_key)

    # Get the transaction witness
    chain1 = copy.deepcopy(chain)
    vm1 = chain1.get_vm()
    vm1._is_stateless = False

    computation, _ = vm1.apply_transaction(tx)
    transaction_witness = computation.vm_state.access_logs.reads

    vm1.block.header.coinbase = recipient
    block1 = chain1.import_block(vm1.block)
    vm1 = chain1.get_vm()

    assert block1.header.coinbase == recipient
    assert len(block1.get_receipts(vm1.chaindb)) == 1
    with vm1.state.state_db(read_only=True) as state_db1:
        assert state_db1.root_hash == block1.header.state_root

    # (3) Try to create a block by witness
    vm2 = copy.deepcopy(vm)
    transaction_package = (tx, transaction_witness)
    block2, _, _ = vm2.create_block(
        transaction_packages=[transaction_package],
        prev_state_root=block0.header.state_root,
        parent_header=block0.header,
        coinbase=recipient,
    )

    assert len(block2.transactions) == 1
    assert block2.header.block_number == 2
    assert block2.header.coinbase == recipient

    # Check if block2 == block1
    assert block2.header.transaction_root == block1.header.transaction_root
    assert block2.header.gas_used == block1.header.gas_used
    assert block2.header.block_number == block1.header.block_number
    assert block2.header.timestamp == block1.header.timestamp

    assert block2.header.receipt_root == block1.header.receipt_root
    assert block2.header.state_root == block1.header.state_root
    assert block2.hash == block1.hash

    # Check if the given parameters are changed
    assert block0.header.state_root != block2.header.state_root
    assert block0.header.block_number == 1
