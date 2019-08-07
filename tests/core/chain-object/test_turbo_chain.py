"""
some tests that chain correctly manipulates the turbo database
"""
import pytest

from eth_utils.toolz import (
    assoc,
)

from eth.db.block_diff import BlockDiff
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
    imported_block_hash = imported_header.hash

    # sanity check, did the transaction go through?
    assert len(imported_block.transactions) == 1
    state = chain.get_vm(imported_header).state
    assert state.get_storage(CONTRACT_ADDRESS, 0) == 42

    # the actual test, did we write out all the changes which happened?
    base_db = chain.chaindb.db
    diff = BlockDiff.from_db(base_db, imported_block_hash)
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
