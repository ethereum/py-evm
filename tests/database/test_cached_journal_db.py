import pytest
from evm.db.backends.memory import MemoryDB
from evm.db.cached_journal import CachedJournalDB

@pytest.fixture
def memory_db():
    return MemoryDB()

@pytest.fixture
def journal_db(memory_db):
    return CachedJournalDB(memory_db)


def test_set_and_get(journal_db, memory_db):
    journal_db.set(b'1', b'test')

    assert journal_db.get(b'1') == b'test'
    assert not memory_db.exists(b'1')

def test_get_non_existent_value(journal_db):
    with pytest.raises(KeyError):
        journal_db.get(b'does-not-exist')


# TODO: Clarify
# Not sure about this test. In the new model, we probably want to avoid hitting
# the underlying database just to figure out if a key actually exists. So I guess
# deleting a should not immediately raise a KeyError even if the key
# does not exist in the underlying db because simply, we can't tell yet.
# def test_delete_non_existent_value(journal_db):
#     with pytest.raises(KeyError):
#         journal_db.delete(b'does-not-exist')


def test_snapshot_and_revert_with_set(journal_db):
    journal_db.set(b'1', b'test-a')

    assert journal_db.get(b'1') == b'test-a'

    snapshot = journal_db.snapshot()

    journal_db.set(b'1', b'test-b')

    assert journal_db.get(b'1') == b'test-b'

    journal_db.revert(snapshot)

    assert journal_db.get(b'1') == b'test-a'


def test_snapshot_and_revert_with_delete(journal_db):
    journal_db.set(b'1', b'test-a')

    assert journal_db.exists(b'1') is True
    assert journal_db.get(b'1') == b'test-a'

    snapshot = journal_db.snapshot()

    journal_db.delete(b'1')

    assert journal_db.exists(b'1') is False

    journal_db.revert(snapshot)

    assert journal_db.exists(b'1') is True
    assert journal_db.get(b'1') == b'test-a'


def test_revert_clears_reverted_journal_entries(journal_db):
    journal_db.set(b'1', b'test-a')

    assert journal_db.get(b'1') == b'test-a'

    snapshot_a = journal_db.snapshot()

    journal_db.set(b'1', b'test-b')
    journal_db.delete(b'1')
    journal_db.set(b'1', b'test-c')

    assert journal_db.get(b'1') == b'test-c'

    snapshot_b = journal_db.snapshot()

    journal_db.set(b'1', b'test-d')
    journal_db.delete(b'1')
    journal_db.set(b'1', b'test-e')

    assert journal_db.get(b'1') == b'test-e'

    journal_db.revert(snapshot_b)

    assert journal_db.get(b'1') == b'test-c'
    journal_db.delete(b'1')

    assert journal_db.exists(b'1') is False

    journal_db.revert(snapshot_a)

    assert journal_db.get(b'1') == b'test-a'

def test_revert_to_pre_commited_snapshot(journal_db, memory_db):
    journal_db.set(b'1', b'test-a')

    assert journal_db.get(b'1') == b'test-a'

    snapshot = journal_db.snapshot()

    journal_db.set(b'1', b'test-b')

    assert journal_db.get(b'1') == b'test-b'

    snapshot2 = journal_db.snapshot()

    journal_db.set(b'1', b'test-c')

    assert journal_db.get(b'1') == b'test-c'

    snapshot3 = journal_db.snapshot()
    journal_db.commit(snapshot3)

    assert journal_db.get(b'1') == b'test-c'
    assert memory_db.get(b'1') == b'test-c'

    journal_db.revert(snapshot)

    assert journal_db.get(b'1') == b'test-a'
    assert memory_db.get(b'1') == b'test-a'
