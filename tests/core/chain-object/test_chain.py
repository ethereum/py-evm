import pytest
import rlp

from eth_utils import decode_hex

from eth import constants
from eth.abc import MiningChainAPI
from eth.chains.mainnet import MAINNET_GENESIS_HEADER
from eth.chains.ropsten import ROPSTEN_GENESIS_HEADER
from eth.exceptions import (
    TransactionNotFound,
)
from eth.tools.factories.transaction import (
    new_transaction
)
from eth.vm.forks.frontier.blocks import FrontierBlock

from tests.core.fixtures import (
    valid_block_rlp,
)


@pytest.fixture
def chain(chain_without_block_validation):
    return chain_without_block_validation


@pytest.fixture
def valid_chain(chain_with_block_validation):
    return chain_with_block_validation


@pytest.fixture()
def tx(chain, funded_address, funded_address_private_key):
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    vm = chain.get_vm()
    from_ = funded_address
    return new_transaction(vm, from_, recipient, amount, funded_address_private_key)


@pytest.fixture()
def tx2(chain, funded_address, funded_address_private_key):
    recipient = b'\x88' * 20
    amount = 100
    vm = chain.get_vm()
    from_ = funded_address
    return new_transaction(vm, from_, recipient, amount, funded_address_private_key, nonce=1)


@pytest.mark.xfail(reason="modification to initial allocation made the block fixture invalid")
def test_import_block_validation(valid_chain, funded_address, funded_address_initial_balance):
    block = rlp.decode(valid_block_rlp, sedes=FrontierBlock)
    imported_block, _, _ = valid_chain.import_block(block)

    assert len(imported_block.transactions) == 1
    tx = imported_block.transactions[0]
    assert tx.value == 10
    vm = valid_chain.get_vm()
    state = vm.state
    assert state.get_balance(
        decode_hex("095e7baea6a6c7c4c2dfeb977efac326af552d87")) == tx.value
    tx_gas = tx.gas_price * constants.GAS_TX
    assert state.get_balance(funded_address) == (
        funded_address_initial_balance - tx.value - tx_gas)


def test_import_block(chain, tx):
    if hasattr(chain, 'apply_transaction'):
        # working on a Mining chain which can directly apply transactions
        new_block, _, computation = chain.apply_transaction(tx)
        computation.raise_if_error()
    else:
        # working on a non-mining chain, so we have to build the block to apply manually
        new_block, receipts, computations = chain.build_block_with_transactions([tx])
        assert len(computations) == 1
        computations[0].raise_if_error()

    block_import_result = chain.import_block(new_block)
    block = block_import_result.imported_block

    assert block.transactions == (tx,)
    assert chain.get_block_by_hash(block.hash) == block
    assert chain.get_canonical_block_by_number(block.number) == block
    assert chain.get_canonical_transaction(tx.hash) == tx


def test_mine_all(chain, tx, tx2, funded_address):
    if hasattr(chain, 'mine_all'):
        start_balance = chain.get_vm().state.get_balance(funded_address)

        mine_result = chain.mine_all([tx, tx2])
        block = mine_result[0].imported_block

        assert block.transactions == (tx, tx2)
        assert chain.get_block_by_hash(block.hash) == block
        assert chain.get_canonical_block_by_number(block.number) == block
        assert chain.get_canonical_transaction(tx.hash) == tx

        end_balance = chain.get_vm().state.get_balance(funded_address)
        expected_spend = 2 * (100 + 21000 * 10)  # sent + gas * gasPrice

        assert start_balance - end_balance == expected_spend
    elif isinstance(chain, MiningChainAPI):
        raise AssertionError()  # Mining chains should have the 'mine_all' method


def test_mine_all_uncle(chain, tx, tx2, funded_address):
    if hasattr(chain, 'mine_all'):
        starting_tip = chain.get_canonical_head()
        canonical = chain.mine_all([tx])
        uncled = chain.mine_all([], parent_header=starting_tip)
        uncled_header = uncled[0].imported_block.header

        new_tip = chain.mine_all(
            [tx2],
            parent_header=canonical[0].imported_block.header,
            uncles=[uncled_header],
        )

        block = new_tip[0].imported_block

        assert block.transactions == (tx2,)
        assert chain.get_block_by_hash(block.hash) == block
        assert block.uncles == (uncled_header,)
    elif isinstance(chain, MiningChainAPI):
        raise AssertionError()  # Mining chains should have the 'mine_all' method


def test_empty_transaction_lookups(chain):
    with pytest.raises(TransactionNotFound):
        chain.get_canonical_transaction(b'\0' * 32)


@pytest.mark.xfail(reason="modification to initial allocation made the block fixture invalid")
def test_canonical_chain(valid_chain):
    genesis_header = valid_chain.chaindb.get_canonical_block_header_by_number(
        constants.GENESIS_BLOCK_NUMBER)

    # Our chain fixture is created with only the genesis header, so initially that's the head of
    # the canonical chain.
    assert valid_chain.get_canonical_head() == genesis_header

    block = rlp.decode(valid_block_rlp, sedes=FrontierBlock)
    valid_chain.chaindb.persist_header(block.header)

    assert valid_chain.get_canonical_head() == block.header
    canonical_block_1 = valid_chain.chaindb.get_canonical_block_header_by_number(
        constants.GENESIS_BLOCK_NUMBER + 1)
    assert canonical_block_1 == block.header


def test_mainnet_genesis_hash():
    assert MAINNET_GENESIS_HEADER.hash == decode_hex(
        '0xd4e56740f876aef8c010b86a40d5f56745a118d0906a34e69aec8c0db1cb8fa3')


def test_ropsten_genesis_hash():
    assert ROPSTEN_GENESIS_HEADER.hash == decode_hex(
        '0x41941023680923e0fe4d74a34bdac8141f2540e3ae90623718e47d66d1ca4a2d')


def test_get_canonical_transaction_by_index(chain, tx):
    if hasattr(chain, 'apply_transaction'):
        # working on a Mining chain which can directly apply transactions
        new_block, _, computation = chain.apply_transaction(tx)
        computation.raise_if_error()
    else:
        # working on a non-mining chain, so we have to build the block to apply manually
        new_block, receipts, computations = chain.build_block_with_transactions([tx])
        assert len(computations) == 1
        computations[0].raise_if_error()

    block_import_result = chain.import_block(new_block)
    block = block_import_result.imported_block

    assert block.transactions == (tx,)
    # transaction at block 1, idx 0
    assert chain.get_canonical_transaction_index(tx.hash) == (1, 0)
    assert chain.get_canonical_transaction_by_index(1, 0) == tx


def test_get_transaction_receipt(chain, tx):
    if hasattr(chain, 'apply_transaction'):
        # working on a Mining chain which can directly apply transactions
        new_block, expected_receipt, computation = chain.apply_transaction(tx)
        computation.raise_if_error()
    else:
        # working on a non-mining chain, so we have to build the block to apply manually
        new_block, receipts, computations = chain.build_block_with_transactions([tx])
        assert len(computations) == 1
        computations[0].raise_if_error()
        expected_receipt = receipts[0]

    block_import_result = chain.import_block(new_block)
    block = block_import_result.imported_block

    assert block.transactions == (tx,)
    # receipt at block 1, idx 0
    assert chain.get_canonical_transaction_index(tx.hash) == (1, 0)
    assert chain.get_transaction_receipt_by_index(1, 0) == expected_receipt
    assert chain.get_transaction_receipt(tx.hash) == expected_receipt
