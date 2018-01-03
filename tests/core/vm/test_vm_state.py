import copy

import pytest

from eth_utils import (
    decode_hex,
)

from evm.db.backends.memory import MemoryDB
from evm.db.chain import BaseChainDB
from evm.vm.forks.frontier.vm_state import FrontierVMState

from tests.core.fixtures import chain_without_block_validation  # noqa: F401
from tests.core.helpers import new_transaction


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
    assert vm.state.block_number == block.header.block_number
    assert vm.state.difficulty == block.header.difficulty
    assert vm.state.gas_limit == block.header.gas_limit


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


def test_apply_transaction(chain_without_block_validation):  # noqa: F811
    chain = chain_without_block_validation  # noqa: F811

    # Don't change these variables
    vm = chain.get_vm()
    vm._is_stateless = False  # Only for testing
    chaindb = copy.deepcopy(vm.chaindb)
    block0 = copy.deepcopy(vm.block)
    block_header0 = copy.deepcopy(vm.block.header)
    initial_state_root = vm.state.block_header.state_root

    # Prepare tx
    vm_example = copy.deepcopy(vm)
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    from_ = chain.funded_address
    tx1 = new_transaction(vm_example, from_, recipient, amount, chain.funded_address_private_key)

    # (1) Get VM level apply_transaction result for assertion
    computation, result_block = vm_example.apply_transaction(tx1)
    chaindb00 = copy.deepcopy(chaindb)
    block_header00 = copy.deepcopy(block_header0)
    vm_state = FrontierVMState(
        chaindb=chaindb00,
        block_header=block_header00,
        is_stateless=True,
    )

    # Use FrontierVMState to apply transaction
    chaindb1 = copy.deepcopy(chaindb)
    block1 = copy.deepcopy(block0)
    block_header1 = block1.header
    vm_state1 = FrontierVMState(
        chaindb=chaindb1,
        block_header=block_header1,
        is_stateless=True,
    )

    computation, block, _ = vm_state1.apply_transaction(
        vm_state1,
        tx1,
        block1,
        witness_db=chaindb1,
    )
    access_logs = computation.vm_state.access_logs
    post_vm_state1 = computation.vm_state

    assert not computation.is_error
    assert len(access_logs.reads) > 0
    assert len(access_logs.writes) > 0

    # Check block data are correct
    assert block.header.state_root == result_block.header.state_root
    assert block.header.gas_limit == result_block.header.gas_limit
    assert block.header.gas_used == result_block.header.gas_used
    assert block.header.transaction_root == result_block.header.transaction_root
    assert block.header.receipt_root == result_block.header.receipt_root

    # Make sure that block1 hasn't been changed
    assert block1.header.state_root == initial_state_root

    # Make sure that vm_state1 hasn't been changed
    assert post_vm_state1.block_header.state_root == result_block.header.state_root
    assert post_vm_state1.block_header.state_root != vm_state1.block_header.state_root

    # (2) Testing using witness as db data
    # Witness_db
    block2 = copy.deepcopy(block0)
    block_header2 = block2.header
    witness_db = BaseChainDB(MemoryDB(access_logs.reads))
    vm_state2 = FrontierVMState(
        chaindb=witness_db,
        block_header=block_header2,
        is_stateless=True,
    )
    # Before applying
    assert post_vm_state1.block_header.state_root != vm_state2.block_header.state_root

    # Applying transaction
    computation, block, _ = vm_state.apply_transaction(
        vm_state2,
        tx1,
        block2,
        witness_db=witness_db,
    )
    post_vm_state2 = computation.vm_state

    # After applying
    # assert post_vm_state2.block_header.state_root == result_block.block_header.state_root
    assert block.header.state_root == post_vm_state2.block_header.state_root
    assert block.header.transaction_root == result_block.header.transaction_root
    assert block.header.receipt_root == result_block.header.receipt_root
    assert block.hash == result_block.hash

    # (3) Testing using witness_db and block_header to reconstruct vm_state
    vm_state3 = FrontierVMState(
        chaindb=witness_db,
        block_header=block.header,
        is_stateless=True,
    )
    assert vm_state3.block_header.state_root == post_vm_state1.block_header.state_root
    assert vm_state3.block_header.state_root == result_block.header.state_root
