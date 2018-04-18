import pytest
from evm.db.backends.memory import MemoryDB
from evm.db.journal import JournalDB

@pytest.fixture
def memory_db():
    return MemoryDB()

@pytest.fixture
def journal_db(memory_db):
    db = JournalDB(memory_db)
    db.snapshot()
    return db


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

def test_commit_shrinks_snapshot_count(journal_db, memory_db):

    snapshot = journal_db.snapshot()
    assert len(journal_db.journal.journal_data) == 2

    journal_db.set(b'1', b'test-a')
    assert journal_db.get(b'1') == b'test-a'

    journal_db.commit(snapshot)

    assert len(journal_db.journal.journal_data) == 1
    assert journal_db.journal.has_checkpoint(snapshot) is False


def test_can_have_empty_snapshots(journal_db, memory_db):

    assert len(journal_db.journal.journal_data) == 1

    snapshot = journal_db.snapshot()
    assert len(journal_db.journal.journal_data) == 2
    
    snapshot2 = journal_db.snapshot()
    assert len(journal_db.journal.journal_data) == 3

    journal_db.set(b'1', b'test-a')
    assert journal_db.get(b'1') == b'test-a'
    assert memory_db.exists(b'1') is False

    journal_db.commit_all()
    assert len(journal_db.journal.journal_data) == 0
    assert memory_db.get(b'1') == b'test-a'


# def test_can_commit_snapshots_in_between(journal_db, memory_db):
#     snapshot = journal_db.snapshot()
#     journal_db.set(b'1', b'test-a')
#     assert journal_db.get(b'1') == b'test-a'
#     assert memory_db.exists(b'1') is False

#     snapshot2 = journal_db.snapshot()

#     journal_db.set(b'1', b'test-b')
#     assert journal_db.get(b'1') == b'test-b'
#     assert memory_db.exists(b'1') is False

#     journal_db.commit(snapshot)
#     raise Exception((snapshot, journal_db.journal.journal_data))
#     assert memory_db.get(b'1') == b'test-a'
