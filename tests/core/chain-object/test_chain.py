import pytest
import rlp

from eth_utils import decode_hex

from evm import constants
from evm.chains.mainnet import MAINNET_GENESIS_HEADER
from evm.chains.ropsten import ROPSTEN_GENESIS_HEADER
from evm.estimators.gas import binary_gas_search_1000_tolerance
from evm.exceptions import (
    TransactionNotFound,
)
from evm.vm.forks.frontier.blocks import FrontierBlock

from tests.core.fixtures import (  # noqa: F401
    valid_block_rlp,
    chaindb,
)
from tests.core.helpers import (
    fill_block,
    new_transaction,
)


ADDRESS_2 = b'\0' * 19 + b'\x02'


@pytest.fixture()
def tx(chain, funded_address, funded_address_private_key):
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    vm = chain.get_vm()
    from_ = funded_address
    return new_transaction(vm, from_, recipient, amount, funded_address_private_key)


def test_apply_transaction(chain, tx):
    vm = chain.get_vm()

    computation = chain.apply_transaction(tx)

    # Check if the state is updated.
    vm = chain.get_vm()
    assert vm.state.state_root == computation.state.state_root
    assert vm.state.read_only_state_db.get_balance(tx.to) == tx.value


def test_import_block_validation(valid_chain, funded_address, funded_address_initial_balance):
    block = rlp.decode(valid_block_rlp, sedes=FrontierBlock)
    imported_block = valid_chain.import_block(block)
    assert len(imported_block.transactions) == 1
    tx = imported_block.transactions[0]
    assert tx.value == 10
    vm = valid_chain.get_vm()
    state_db = vm.state.read_only_state_db
    assert state_db.get_balance(
        decode_hex("095e7baea6a6c7c4c2dfeb977efac326af552d87")) == tx.value
    tx_gas = tx.gas_price * constants.GAS_TX
    assert state_db.get_balance(funded_address) == (
        funded_address_initial_balance - tx.value - tx_gas)


def test_import_block(chain, tx):
    vm = chain.get_vm()
    computation, _ = vm.apply_transaction(tx)
    assert not computation.is_error

    # add pending so that we can confirm it gets removed when imported to a block
    chain.add_pending_transaction(tx)

    block = chain.import_block(vm.block)
    assert block.transactions == [tx]
    assert chain.get_block_by_hash(block.hash) == block
    assert chain.get_canonical_block_by_number(block.number) == block
    assert chain.get_canonical_transaction(tx.hash) == tx

    with pytest.raises(TransactionNotFound):
        # after mining, the transaction shouldn't be in the pending set anymore
        chain.get_pending_transaction(tx.hash)


def test_get_pending_transaction(chain, tx):
    chain.add_pending_transaction(tx)
    assert chain.get_pending_transaction(tx.hash) == tx


def test_empty_transaction_lookups(chain):

    with pytest.raises(TransactionNotFound):
        chain.get_canonical_transaction(b'\0' * 32)

    with pytest.raises(TransactionNotFound):
        chain.get_pending_transaction(b'\0' * 32)


@pytest.fixture(
    params=[True, False])
def unsigned_or_signed_tx(request):
    def tx(
            vm,
            from_,
            to,
            amount,
            private_key=None,
            gas_price=10,
            gas=100000,
            data=b''):

        if request.param:
            return new_transaction(
                vm,
                from_,
                to,
                amount,
                private_key,
                gas_price,
                gas,
                data)

        else:
            return new_transaction(
                vm,
                from_,
                to,
                amount,
                private_key=None,
                gas_price=gas_price,
                gas=gas,
                data=data)
    return tx


@pytest.mark.parametrize(
    'data, gas_estimator, to, on_pending, expected',
    (
        (b'', None, None, True, 21000),
        (b'', None, None, False, 21000),
        (b'\xff' * 10, None, None, True, 21680),
        (b'\xff' * 10, None, None, False, 21680),
        # sha3 precompile
        (b'\xff' * 32, None, ADDRESS_2, True, 35381),
        (b'\xff' * 32, None, ADDRESS_2, False, 35369),
        (b'\xff' * 320, None, ADDRESS_2, True, 54888),
        # 1000_tolerance binary search
        (b'\xff' * 32, binary_gas_search_1000_tolerance, ADDRESS_2, True, 23938),
    ),
    ids=[
        'simple default pending',
        'simple default',
        '10 bytes default pending',
        '10 bytes default',
        'sha3 precompile 32 bytes default pending',
        'sha3 precompile 32 bytes default',
        'sha3 precompile 320 bytes default pending',
        'sha3 precompile 32 bytes 1000_tolerance binary pending',
    ],
)
def test_estimate_gas(
        chain,
        data,
        gas_estimator,
        to,
        on_pending,
        expected,
        funded_address,
        funded_address_private_key,
        unsigned_or_signed_tx):
    if gas_estimator:
        chain.gas_estimator = gas_estimator
    vm = chain.get_vm()
    if to:
        recipient = to
    else:
        recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100
    from_ = funded_address
    tx = unsigned_or_signed_tx(vm, from_, recipient, amount, funded_address_private_key, data=data)
    if on_pending:
        # estimate on *pending* block
        assert chain.estimate_gas(tx, chain.header) == expected
    else:
        # estimates on top of *latest* block
        assert chain.estimate_gas(tx) == expected
        # these are long, so now that we know the exact numbers let's skip the repeat test
        # assert chain.estimate_gas(tx, chain.get_canonical_head()) == expected


def test_estimate_gas_on_full_block(chain, funded_address_private_key, funded_address):

    def estimation_txn(chain, from_, from_key, data):
        to = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
        gas = chain.header.gas_limit
        amount = 200
        vm = chain.get_vm()
        return new_transaction(vm, from_, to, amount, from_key, gas=gas, data=data)

    from_ = funded_address
    from_key = funded_address_private_key
    garbage_data = b"""
        fill up the block much faster because this transaction contains a bunch of extra
        garbage_data, which doesn't add to execution time, just the gas costs
    """ * 30
    gas = 375000

    # fill the canonical head
    fill_block(chain, from_, from_key, gas, garbage_data)
    chain.import_block(chain.get_vm().block)

    # build a transaction to estimate gas for
    next_canonical_tx = estimation_txn(chain, from_, from_key, data=garbage_data * 2)

    assert chain.estimate_gas(next_canonical_tx) == 722760

    # fill the pending block
    fill_block(chain, from_, from_key, gas, garbage_data)

    # build a transaction to estimate gas for
    next_pending_tx = estimation_txn(chain, from_, from_key, data=garbage_data * 2)

    assert chain.estimate_gas(next_pending_tx, chain.header) == 722760


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
