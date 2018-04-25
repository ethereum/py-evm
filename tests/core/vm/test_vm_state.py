import copy

import pytest

from eth_utils import (
    decode_hex,
)

from evm.exceptions import DecommissionedStateDB
from evm.vm.forks.spurious_dragon.state import SpuriousDragonState

from tests.core.helpers import new_transaction


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


def test_state_db(state):
    address = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    initial_state_root = state.state_root

    # test cannot write to state_db after context exits
    with state.mutable_state_db() as state_db:
        pass

    with pytest.raises(DecommissionedStateDB):
        state_db.increment_nonce(address)

    state.read_only_state_db.get_balance(address)
    assert state.state_root == initial_state_root

    with state.mutable_state_db() as state_db:
        state_db.set_balance(address, 10)
    assert state.state_root != initial_state_root

    with pytest.raises(TypeError):
        state.read_only_state_db.set_balance(address, 0)


def test_apply_transaction(
        chain_without_block_validation,
        funded_address,
        funded_address_private_key):
    chain = chain_without_block_validation

    # Don't change these variables
    vm = chain.get_vm()
    chaindb = copy.deepcopy(vm.chaindb)
    block0 = copy.deepcopy(vm.block)
    prev_block_hash = chain.get_canonical_block_by_number(0).hash
    initial_state_root = vm.block.header.state_root

    # (1) Get VM.apply_transaction(transaction) result for assertion
    # The first transaction
    chain1 = copy.deepcopy(chain)
    vm_example = chain1.get_vm()
    recipient1 = decode_hex('0x1111111111111111111111111111111111111111')
    amount = 100
    from_ = funded_address
    tx1 = new_transaction(
        vm_example,
        from_,
        recipient1,
        amount,
        private_key=funded_address_private_key,
    )
    computation, result_block = vm_example.apply_transaction(tx1)

    # The second transaction
    recipient2 = decode_hex('0x2222222222222222222222222222222222222222')
    tx2 = new_transaction(
        vm_example,
        from_,
        recipient2,
        amount,
        private_key=funded_address_private_key,
    )
    computation, result_block = vm_example.apply_transaction(tx2)
    assert len(result_block.transactions) == 2

    # (2) Test State.apply_transaction(...)
    # Use SpuriousDragonState to apply transaction
    chaindb1 = copy.deepcopy(chaindb)
    block1 = copy.deepcopy(block0)
    prev_hashes = vm.get_prev_hashes(
        last_block_hash=prev_block_hash,
        db=vm.chaindb,
    )
    execution_context = block1.header.create_execution_context(prev_hashes)
    state1 = SpuriousDragonState(
        chaindb=chaindb1,
        execution_context=execution_context,
        state_root=block1.header.state_root,
        gas_used=0,
    )
    parent_hash = copy.deepcopy(prev_hashes[0])

    computation, block, _ = state1.apply_transaction(
        tx1,
        block1,
    )

    # Check if prev_hashes hasn't been changed
    assert parent_hash == prev_hashes[0]
    # Make sure that block1 hasn't been changed
    assert block1.header.state_root == initial_state_root
    execution_context = block.header.create_execution_context(prev_hashes)
    state1 = SpuriousDragonState(
        chaindb=chaindb1,
        execution_context=execution_context,
        state_root=block.header.state_root,
        gas_used=computation.state.gas_used,
    )
    computation, block, _ = state1.apply_transaction(
        tx2,
        block,
    )
    post_state = computation.state

    # Check block data are correct
    assert block.header.state_root == result_block.header.state_root
    assert block.header.gas_limit == result_block.header.gas_limit
    assert block.header.gas_used == result_block.header.gas_used
    assert block.header.transaction_root == result_block.header.transaction_root
    assert block.header.receipt_root == result_block.header.receipt_root

    # Make sure that state1 hasn't been changed
    assert post_state.state_root == result_block.header.state_root
