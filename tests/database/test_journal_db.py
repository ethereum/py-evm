import pytest
from evm.db.backends.memory import MemoryDB
from evm.db.journal import JournalDB

@pytest.fixture
def memory_db():
    return MemoryDB()

@pytest.fixture
def journal_db(memory_db):
    return JournalDB(memory_db)


def test_snapshot_and_revert_with_set(journal_db):
    journal_db.set(b'1', b'test-a')

    assert journal_db.get(b'1') == b'test-a'

    changeset = journal_db.record()

    journal_db.set(b'1', b'test-b')

    assert journal_db.get(b'1') == b'test-b'

    journal_db.forget(changeset)

    assert journal_db.get(b'1') == b'test-a'


def test_snapshot_and_revert_with_delete(journal_db):
    journal_db.set(b'1', b'test-a')

    assert journal_db.exists(b'1') is True
    assert journal_db.get(b'1') == b'test-a'

    changeset = journal_db.record()

    journal_db.delete(b'1')

    assert journal_db.exists(b'1') is False

    journal_db.forget(changeset)

    assert journal_db.exists(b'1') is True
    assert journal_db.get(b'1') == b'test-a'


def test_revert_clears_reverted_journal_entries(journal_db):
    journal_db.set(b'1', b'test-a')

    assert journal_db.get(b'1') == b'test-a'

    changeset_a = journal_db.record()

    journal_db.set(b'1', b'test-b')
    journal_db.delete(b'1')
    journal_db.set(b'1', b'test-c')

    assert journal_db.get(b'1') == b'test-c'

    changeset_b = journal_db.record()

    journal_db.set(b'1', b'test-d')
    journal_db.delete(b'1')
    journal_db.set(b'1', b'test-e')

    assert journal_db.get(b'1') == b'test-e'

    journal_db.forget(changeset_b)

    assert journal_db.get(b'1') == b'test-c'

    journal_db.delete(b'1')

    assert journal_db.exists(b'1') is False

    journal_db.forget(changeset_a)

    assert journal_db.get(b'1') == b'test-a'

def test_revert_removes_journal_entries(journal_db):

    changeset_a = journal_db.record()
    assert len(journal_db.journal.journal_data) == 2

    changeset_b = journal_db.record()
    assert len(journal_db.journal.journal_data) == 3

    # Forget *latest* changeset and prove it's the only one removed
    journal_db.forget(changeset_b)
    assert len(journal_db.journal.journal_data) == 2

    changeset_b2 = journal_db.record()
    assert len(journal_db.journal.journal_data) == 3

    changeset_c = journal_db.record()
    assert len(journal_db.journal.journal_data) == 4

    changeset_d = journal_db.record()
    assert len(journal_db.journal.journal_data) == 5

    # Forget everything from b2 (inclusive) and what follows
    journal_db.forget(changeset_b2)
    assert len(journal_db.journal.journal_data) == 2
    assert journal_db.journal.has_checkpoint(changeset_b2) is False


def test_commit_merges_changeset_into_previous(journal_db):

    changeset = journal_db.record()
    assert len(journal_db.journal.journal_data) == 2

    journal_db.set(b'1', b'test-a')
    assert journal_db.get(b'1') == b'test-a'

    journal_db.commit(changeset)

    assert len(journal_db.journal.journal_data) == 1
    assert journal_db.journal.has_checkpoint(changeset) is False

def test_committing_middle_changeset_merges_in_subsequent_changesets(journal_db):

    journal_db.set(b'1', b'test-a')
    changeset_a = journal_db.record()
    assert len(journal_db.journal.journal_data) == 2

    journal_db.set(b'1', b'test-b')
    changeset_b = journal_db.record()
    assert len(journal_db.journal.journal_data) == 3

    journal_db.set(b'1', b'test-c')
    changeset_c = journal_db.record()
    assert len(journal_db.journal.journal_data) == 4

    # TODO: Clarify
    # This seems counterintuitive to me. Why does commiting to changeset_b
    # Mean we are implicitly commiting to subsequent changesets?
    # Why don't we just merge b into a but keep c seperate?
    journal_db.commit(changeset_b)
    assert journal_db.get(b'1') == b'test-c'
    assert len(journal_db.journal.journal_data) == 2
    assert journal_db.journal.has_checkpoint(changeset_a)
    assert journal_db.journal.has_checkpoint(changeset_b) is False
    assert journal_db.journal.has_checkpoint(changeset_c) is False


def test_commit_all_writes_to_underlying_db(journal_db, memory_db):
    changeset = journal_db.record()
    journal_db.set(b'1', b'test-a')
    assert journal_db.get(b'1') == b'test-a'
    assert memory_db.exists(b'1') is False

    changeset_b = journal_db.record()

    journal_db.set(b'1', b'test-b')
    assert journal_db.get(b'1') == b'test-b'
    assert memory_db.exists(b'1') is False

    journal_db.commit_all()
    assert len(journal_db.journal.journal_data) == 0
    assert memory_db.get(b'1') == b'test-b'

