import pytest

from eth_utils import int_to_big_endian

from eth_hash.auto import keccak

from eth.constants import BLANK_ROOT_HASH
from eth.db.atomic import AtomicDB
from eth.db.block_diff import BlockDiff
from eth.db.account import AccountDB
from eth.db.storage import StorageLookup

ACCOUNT = b'\xaa' * 20
BLOCK_HASH = keccak(b'one')

"""
TODO: Some tests remain to be written:
- Are we sure that old accounts are being recorded? Start from an account which already has a value
  and check that it is saved.
- Check that deleting an account is correctly saved.
- Test that this behavior is trigger during block import (if Turbo-mode is enabled)
- Test for more fields, such as account balances.
- Test that this works even under calls to things like commit() and snapshot()
- Test that these diffs can be applied to something and the correct resulting state obtained
"""


@pytest.fixture
def base_db():
    return AtomicDB()


@pytest.fixture
def account_db(base_db):
    return AccountDB(base_db)


# Some basic tests that BlockDiff works as expected and can round-trip data to the database


def test_no_such_diff_raises_key_error(base_db):
    with pytest.raises(KeyError):
        BlockDiff.from_db(base_db, BLOCK_HASH)


def test_can_persist_empty_block_diff(base_db):
    orig = BlockDiff(BLOCK_HASH)
    orig.write_to(base_db)

    block_diff = BlockDiff.from_db(base_db, BLOCK_HASH)
    assert len(block_diff.get_changed_accounts()) == 0


def test_can_persist_changed_account(base_db):
    orig = BlockDiff(BLOCK_HASH)
    orig.set_account_changed(ACCOUNT, b'old', b'new')  # TODO: more realistic data
    orig.write_to(base_db)

    block_diff = BlockDiff.from_db(base_db, BLOCK_HASH)
    assert block_diff.get_changed_accounts() == (ACCOUNT,)
    assert block_diff.get_account(ACCOUNT, new=True) == b'new'
    assert block_diff.get_account(ACCOUNT, new=False) == b'old'


# Some tests that AccountDB saves a block diff when persist()ing


def test_account_diffs(account_db):
    account_db.set_nonce(ACCOUNT, 10)
    account_db.persist_with_block_diff(BLOCK_HASH)

    diff = BlockDiff.from_db(account_db._raw_store_db, BLOCK_HASH)
    assert diff.get_changed_accounts() == (ACCOUNT, )
    new_account = diff.get_decoded_account(ACCOUNT, new=True)
    assert new_account.nonce == 10

    assert diff.get_decoded_account(ACCOUNT, new=False) is None


def test_persists_storage_changes(account_db):
    account_db.set_storage(ACCOUNT, 1, 10)
    account_db.persist_with_block_diff(BLOCK_HASH)

    diff = BlockDiff.from_db(account_db._raw_store_db, BLOCK_HASH)
    assert diff.get_changed_accounts() == (ACCOUNT, )

    key = int_to_big_endian(1)

    # TODO: provide some interface, this shouldn't be reading items directly out of the diff
    assert ACCOUNT in diff.changed_storage_items
    assert tuple(diff.changed_storage_items[ACCOUNT].keys()) == (key,)
    assert diff.changed_storage_items[ACCOUNT][key].old == b''
    assert diff.changed_storage_items[ACCOUNT][key].new == bytes([10])


def test_persists_state_root(account_db):
    """
    When the storage items change the account's storage root also changes and that change also
    needs to be persisted.
    """

    # First, compute the expected new storage root
    db = AtomicDB()
    example_lookup = StorageLookup(db, BLANK_ROOT_HASH, ACCOUNT)
    key = int_to_big_endian(1)
    example_lookup[key] = int_to_big_endian(10)
    expected_root = example_lookup.get_changed_root()

    # Next, make the same change to out storage
    account_db.set_storage(ACCOUNT, 1, 10)
    account_db.persist_with_block_diff(BLOCK_HASH)

    # The new state root should have been included as part of the diff.

    diff = BlockDiff.from_db(account_db._raw_store_db, BLOCK_HASH)
    assert diff.get_changed_accounts() == (ACCOUNT, )
    new_account = diff.get_decoded_account(ACCOUNT, new=True)
    assert new_account.storage_root == expected_root
