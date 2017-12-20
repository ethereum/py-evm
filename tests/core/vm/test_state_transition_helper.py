from eth_utils import (
    decode_hex,
)

from evm import constants
from evm.db.backends.memory import MemoryDB
from evm.db.chain import BaseChainDB
from evm.vm.state_transition_helper import (
    apply_transaction,
)

from tests.core.fixtures import chain_without_block_validation  # noqa: F401
from tests.core.helpers import new_transaction


def test_apply_transaction(chain_without_block_validation):  # noqa: F811
    chain = chain_without_block_validation  # noqa: F811

    # Get original_root_hash for assertion
    original_root_hash = None
    with chain.get_vm().state_db(read_only=True) as state_db:
        original_root_hash = state_db.root_hash
    assert original_root_hash is not None

    vm = chain.get_vm()

    # Prepare a transaction
    tx_idx = len(vm.block.transactions)
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    from_ = chain.funded_address
    tx = new_transaction(vm, from_, recipient, amount, chain.funded_address_private_key)
    tx_gas = tx.gas_price * constants.GAS_TX

    # Apply transaction to vm.block and also return vm.block
    success, reads, writes, block = apply_transaction(
        tx,
        vm.block,
        vm,
        chain.chaindb,
    )

    # Store the witness data in memory
    db = MemoryDB(reads)
    witness_db = BaseChainDB(db)

    assert success
    assert block.transactions[tx_idx] == tx
    assert block.header.gas_used == constants.GAS_TX

    # Check if no side effect, state trie in `chain.chaindb` haven't been changed
    with chain.get_vm().state_db(read_only=True) as chain_state_db:
        assert chain_state_db.root_hash == original_root_hash
        with vm.state_db(read_only=True) as state_db:
            assert state_db.root_hash == original_root_hash

    # Try again - Simulate apply the given transaction package with witness data
    vm = chain.get_vm()

    assert vm.block.transaction_count == 0

    success, reads, writes, block = apply_transaction(
        tx,
        vm.block,
        vm,
        witness_db,
    )
    assert success
    assert block.transactions[tx_idx] == tx
    assert block.header.gas_used == constants.GAS_TX

    # Check if block can be apply to a chain
    chain.import_block(block)
    vm = chain.get_vm()
    with vm.state_db(read_only=True) as state_db:
        assert state_db.get_balance(from_) == (
            chain.funded_address_initial_balance - amount - tx_gas)
        assert state_db.get_balance(recipient) == amount
