import pytest
from evm.db.backends.memory import MemoryDB
from evm.db.journal import JournalDB


@pytest.fixture
def journal_db():
    return JournalDB(MemoryDB())


def test_set_and_get(journal_db):
    journal_db.set(b'1', b'test')

    assert journal_db.get(b'1') == b'test'


def test_get_non_existent_value(journal_db):
    with pytest.raises(KeyError):
        journal_db.get(b'does-not-exist')


def test_delete_non_existent_value(journal_db):
    with pytest.raises(KeyError):
        journal_db.delete(b'does-not-exist')


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
