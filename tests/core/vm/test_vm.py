import copy

import pytest

from eth_utils import decode_hex

from evm import constants

from tests.core.fixtures import chain_without_block_validation  # noqa: F401
from tests.core.helpers import new_transaction


def test_add_transaction_to_block(chain_without_block_validation):  # noqa: F811
    chain = chain_without_block_validation  # noqa: F811
    vm = copy.deepcopy(chain.get_vm())  # Use vm as a temporary container

    # Prepare a transaction
    tx_idx = len(vm.block.transactions)
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    from_ = chain.funded_address
    tx = new_transaction(vm, from_, recipient, amount, chain.funded_address_private_key)
    tx_gas = tx.gas_price * constants.GAS_TX

    # Use add_transaction_to_block as a pure function
    computation = vm.execute_transaction(tx)
    prev_block = copy.deepcopy(vm.block)
    block = vm.add_transaction_to_block(tx, prev_block, computation)

    # Check if no side effect
    assert prev_block.hash != block.hash

    # Check if the result is right
    with vm.state_db(read_only=True) as state_db:
        assert state_db.get_balance(from_) == (
            chain.funded_address_initial_balance - amount - tx_gas)
        assert state_db.get_balance(recipient) == amount

    assert block.transactions[tx_idx] == tx
    assert block.header.gas_used == constants.GAS_TX

    # Check if testing on different VM object
    with vm.state_db(read_only=True) as state_db:
        with chain.get_vm().state_db(read_only=True) as prev_state_db:
            assert state_db.get_balance(from_) != prev_state_db.get_balance(from_)
            assert state_db.get_balance(recipient) != prev_state_db.get_balance(recipient)

    # Block can be apply to a chain
    chain.import_block(block)
    vm = chain.get_vm()
    with vm.state_db(read_only=True) as state_db:
        assert state_db.get_balance(from_) == (
            chain.funded_address_initial_balance - amount - tx_gas)
        assert state_db.get_balance(recipient) == amount


def test_apply_transaction(chain_without_block_validation):  # noqa: F811
    chain = chain_without_block_validation  # noqa: F811
    vm = chain.get_vm()

    # Prepare a transaction
    tx_idx = len(vm.block.transactions)
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    from_ = chain.funded_address
    tx = new_transaction(vm, from_, recipient, amount, chain.funded_address_private_key)
    tx_gas = tx.gas_price * constants.GAS_TX

    computation = vm.apply_transaction(tx)

    # result:
    # 1. computation
    assert not computation.is_error
    # 2. vm.state_db
    with vm.state_db(read_only=True) as state_db:
        assert state_db.get_balance(from_) == (
            chain.funded_address_initial_balance - amount - tx_gas)
        assert state_db.get_balance(recipient) == amount
    # 3. vm.block
    block = vm.block
    assert block.transactions[tx_idx] == tx
    assert block.header.gas_used == constants.GAS_TX


def test_apply_transaction_semi_pure(chain_without_block_validation):  # noqa: F811
    chain = chain_without_block_validation  # noqa: F811
    vm = copy.deepcopy(chain.get_vm())  # Use vm as a temporary container

    # Prepare a transaction
    tx_idx = len(vm.block.transactions)
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    from_ = chain.funded_address
    tx = new_transaction(vm, from_, recipient, amount, chain.funded_address_private_key)
    tx_gas = tx.gas_price * constants.GAS_TX

    # chaindb: a db object, TODO: use TrackedDB
    # block: the current block blocked
    chaindb = copy.deepcopy(chain.chaindb)
    block = copy.deepcopy(vm.block)

    computation, block = vm.apply_transaction_to_block(tx, chaindb, block)

    # result:
    # 1. computation
    assert computation.error is None
    # 2. vm.state_db
    with vm.state_db(read_only=True) as state_db:
        assert state_db.get_balance(from_) == (
            chain.funded_address_initial_balance - amount - tx_gas)
        assert state_db.get_balance(recipient) == amount
    # 3. vm.block
    assert block.transactions[tx_idx] == tx
    assert block.header.gas_used == constants.GAS_TX


# def test_apply_block(chain_without_block_validation):  # noqa: F811
#     chain = chain_without_block_validation  # noqa: F811
#     vm = chain.get_vm()
#     recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
#     amount = 100
#     from_ = chain.funded_address
#     tx = new_transaction(vm, from_, recipient, amount, chain.funded_address_private_key)
#     computation = vm.apply_transaction(tx)
#     assert computation.error is None

#     parent_vm = chain.get_chain_at_block_parent(vm.block).get_vm()
#     chaindb = copy.deepcopy(chain.chaindb)
#     block = parent_vm.apply_block(vm.block, chaindb)
#     assert block.transactions == [tx]

#     # [TODO]: more tests


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
    assert not computation.is_error
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

    with pytest.raises(TypeError):
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
