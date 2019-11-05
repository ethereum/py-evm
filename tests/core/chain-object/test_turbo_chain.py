"""
some tests that chain correctly manipulates the turbo database
"""
import pytest

from eth_utils.toolz import (
    assoc,
)
from eth_hash.auto import keccak

import rlp

from eth.rlp.accounts import Account

from eth.chains.base import MiningChain
from eth.db.block_diff import BlockDiff
from eth.db.schema import SchemaTurbo
from eth.tools._utils.vyper import (
    compile_vyper_lll,
)

from tests.core.helpers import (
    new_transaction,
)


CONTRACT_ADDRESS = b'\x10' * 20


@pytest.fixture
def genesis_state(base_genesis_state):
    """
    A little bit of magic, this overrides the genesis_state fixture which was defined elsewhere so
    chain_without_block_validation uses the genesis state specified here.
    """

    # 1. when called this contract makes a simple change to the state
    code = ['SSTORE', 0, 42]
    bytecode = compile_vyper_lll(code)[0]

    # 2. put that code somewhere useful
    return assoc(
        base_genesis_state,
        CONTRACT_ADDRESS,
        {
            'balance': 0,
            'nonce': 0,
            'code': bytecode,
            'storage': {},
        }
    )


@pytest.fixture
def chain(chain_without_block_validation):
    # make things a little less verbose
    return chain_without_block_validation


def test_import_block_saves_block_diff(chain, funded_address, funded_address_private_key):
    tx = new_transaction(
        chain.get_vm(),
        funded_address,
        CONTRACT_ADDRESS,
        data=b'',
        private_key=funded_address_private_key,
    )

    new_block, _, _ = chain.build_block_with_transactions([tx])
    imported_block, _, _ = chain.import_block(new_block)

    imported_header = imported_block.header
    imported_block_state_root = imported_header.state_root

    # sanity check, did the transaction go through?
    assert len(imported_block.transactions) == 1
    state = chain.get_vm(imported_header).state
    assert state.get_storage(CONTRACT_ADDRESS, 0) == 42

    # the actual test, did we write out all the changes which happened?
    base_db = chain.chaindb.db
    diff = BlockDiff.from_db(base_db, imported_block_state_root)
    assert len(diff.get_changed_accounts()) == 3
    assert CONTRACT_ADDRESS in diff.get_changed_accounts()
    assert imported_header.coinbase in diff.get_changed_accounts()
    assert funded_address in diff.get_changed_accounts()

    assert diff.get_changed_slots(CONTRACT_ADDRESS) == {0}
    assert diff.get_slot_change(CONTRACT_ADDRESS, 0) == (0, 42)

    assert diff.get_changed_slots(funded_address) == set()
    assert diff.get_changed_slots(imported_header.coinbase) == set()

    # do some spot checks to make sure different fields were saved

    assert diff.get_decoded_account(imported_header.coinbase, new=False) is None
    new_coinbase_balance = diff.get_decoded_account(imported_header.coinbase, new=True).balance
    assert new_coinbase_balance > 0

    old_sender_balance = diff.get_decoded_account(funded_address, new=False).balance
    new_sender_balance = diff.get_decoded_account(funded_address, new=True).balance
    assert old_sender_balance > new_sender_balance

    old_contract_nonce = diff.get_decoded_account(CONTRACT_ADDRESS, new=False).nonce
    new_contract_nonce = diff.get_decoded_account(CONTRACT_ADDRESS, new=True).nonce
    assert old_contract_nonce == 0
    assert new_contract_nonce == 0


# TODO: This belongs somewhere in the actual code, not in the tests. What kind of
# interface would make interacting with the turbodb easier?
def read_account_from_db(base_db, address):
    key = SchemaTurbo.make_account_state_lookup_key(keccak(address))

    try:
        account_rlp = base_db[key]
    except KeyError:
        return Account()

    if account_rlp == b'':
        return Account()

    return rlp.decode(account_rlp, sedes=Account)


def test_import_multiple_txns_saves_complete_block_diff(chain, funded_address, funded_address_private_key):
    """
    MiningChain builds a new VM each time a method (such as apply_transaction) is called.

    block diffs are created by AccountDB, and there isn't a good way of tracking changes
    over multiple instance of AccountDB. This means that block diffs created by the later
    VM instances will be incomplete, they'll miss any accounts which changed in previous
    VM instances.

    It turns out that this isn't actually a problem, because the VM which builds the block
    diff is created during `chain.import_block`, it re-runs every transaction and then
    saves the block diff.

    Keeping this test because that's kind of an inefficient implementation detail and
    might change. Once it changes this test will start failing. I think the right fix is
    a refactor to MiningChain. It ought to keep around a single pending VM and apply all
    transactions to that VM. This way the AccountDB will have seen all changes, so it can
    emit an accurate block diff. This refactor can also be expected to improve test
    performance.
    """
    if not isinstance(chain, MiningChain):
        pytest.skip('this test checks that MiningChain works properly')

    FIRST_ADDRESS = b'\x10' * 20
    SECOND_ADDRESS = b'\x20' * 20

    # 1. Make a txn which changes one account
    first_txn = new_transaction(
        chain.get_vm(),
        funded_address,
        FIRST_ADDRESS,
        data=b'',
        private_key=funded_address_private_key,
        amount=1000,
    )
    chain.apply_transaction(first_txn)

    # 2. Make a txn which changes a second account
    second_txn = new_transaction(
        chain.get_vm(),
        funded_address,
        SECOND_ADDRESS,
        data=b'',
        private_key=funded_address_private_key,
        amount=1000,
    )
    new_block, _receipt, _computation = chain.apply_transaction(second_txn)
    mined_block, _, _ = chain.import_block(new_block)

    # did the transactions go through?
    assert mined_block.transactions == (first_txn, second_txn)

    # what does the block diff say?
    base_db = chain.chaindb.db
    diff = BlockDiff.from_db(base_db, mined_block.header.state_root)
    assert diff.get_changed_accounts() == {
        funded_address,
        FIRST_ADDRESS,
        SECOND_ADDRESS,
        mined_block.header.coinbase,
    }

    first_account = read_account_from_db(base_db, FIRST_ADDRESS)
    assert first_account.balance == 1000


def test_block_reorgs(chain, funded_address, funded_address_private_key):
    """
    A1 - B1
       \ B2 - C2
    """
    base_db = chain.chaindb.db

    A1_ADDRESS = b'\x10' * 20
    B1_ADDRESS = b'\x20' * 20
    B2_ADDRESS = b'\x30' * 20
    C2_ADDRESS = b'\x40' * 20

    def make_transaction_to(destination_address, amount, parent_header=None):
        return new_transaction(
            chain.get_vm(parent_header),
            funded_address,
            destination_address,
            data=b'',
            private_key=funded_address_private_key,
            amount=amount,
        )

    # The account starts out empty
    assert read_account_from_db(base_db, A1_ADDRESS).balance == 0

    # After we import A1 the address has some wei
    A1_transaction = make_transaction_to(A1_ADDRESS, 1000)
    new_A1, _, _ = chain.build_block_with_transactions([A1_transaction])
    imported_A1, _, _ = chain.import_block(new_A1)
    assert read_account_from_db(base_db, A1_ADDRESS).balance == 1000
    assert read_account_from_db(base_db, funded_address).nonce == 1

    # After we import B1 the second address also has some wei
    B1_transaction = make_transaction_to(B1_ADDRESS, 1000)
    new_B1, _, _ = chain.build_block_with_transactions([B1_transaction])
    imported_B1, _, _ = chain.import_block(new_B1)
    assert read_account_from_db(base_db, A1_ADDRESS).balance == 1000
    assert read_account_from_db(base_db, B1_ADDRESS).balance == 1000
    assert read_account_from_db(base_db, funded_address).nonce == 2

    # Import a competing block. No asserts because it's not clear which one should win
    B2_transaction = make_transaction_to(B2_ADDRESS, 1000, imported_A1.header)
    new_B2, _, _ = chain.build_block_with_transactions(
        [B2_transaction], parent_header=imported_A1.header
    )
    imported_B2, _, _ = chain.import_block(new_B2)

    # Importing C2 causes a re-org which should reshuffle some state around
    C2_transaction = make_transaction_to(C2_ADDRESS, 1000, imported_B2.header)
    new_C2, _, _ = chain.build_block_with_transactions(
        [C2_transaction], parent_header=imported_B2.header
    )
    imported_C2, _, _ = chain.import_block(new_C2)
    assert read_account_from_db(base_db, A1_ADDRESS).balance == 1000
    assert read_account_from_db(base_db, B1_ADDRESS).balance == 0
    assert read_account_from_db(base_db, B2_ADDRESS).balance == 1000
    assert read_account_from_db(base_db, C2_ADDRESS).balance == 1000
    assert read_account_from_db(base_db, funded_address).nonce == 3
