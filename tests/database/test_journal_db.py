from uuid import uuid4

from eth_utils import ValidationError
from hypothesis import (
    given,
    strategies as st,
)
import pytest

from eth.db.backends.memory import MemoryDB
from eth.db.journal import JournalDB


@pytest.fixture
def memory_db():
    return MemoryDB()


@pytest.fixture
def journal_db(memory_db):
    return JournalDB(memory_db)


def test_delete_removes_data_from_underlying_db_after_persist(journal_db, memory_db):
    memory_db.set(b'1', b'test-a')

    assert memory_db.exists(b'1') is True

    journal_db.delete(b'1')
    assert memory_db.exists(b'1') is True
    journal_db.persist()

    assert memory_db.exists(b'1') is False


def test_clear_leaves_data_in_underlying_db_after_persist(journal_db, memory_db):
    """
    JournalDB.clear() can't assume that it can iterate all underlying keys, so it
    can't know which data to delete on disk. Instead, clear() is only responsible
    for deleting all changes that came before it.
    """
    memory_db.set(b'underlying-untouched', b'exists')
    memory_db.set(b'underlying-modified', b'unchanged')

    journal_db.set(b'new-before-clear', b'never added')
    journal_db.set(b'underlying-modified', b'dropped')
    journal_db.clear()
    journal_db.set(b'after-clear', b'added')

    journal_db.persist()

    assert memory_db[b'underlying-untouched'] == b'exists'
    assert memory_db[b'underlying-modified'] == b'unchanged'
    with pytest.raises(KeyError):
        memory_db[b'new-before-clear']
    assert memory_db[b'after-clear'] == b'added'


def test_snapshot_and_revert_with_set(journal_db):
    journal_db.set(b'1', b'test-a')

    assert journal_db.get(b'1') == b'test-a'

    changeset = journal_db.record()

    journal_db.set(b'1', b'test-b')

    assert journal_db.get(b'1') == b'test-b'

    journal_db.discard(changeset)

    assert journal_db.get(b'1') == b'test-a'


def test_custom_snapshot_and_revert_with_set(journal_db):
    journal_db.set(b'1', b'test-a')

    assert journal_db.get(b'1') == b'test-a'

    custom_changeset = uuid4()
    changeset = journal_db.record(custom_changeset)

    assert journal_db.has_changeset(custom_changeset)
    assert changeset == custom_changeset

    journal_db.set(b'1', b'test-b')

    assert journal_db.get(b'1') == b'test-b'

    journal_db.discard(changeset)

    assert not journal_db.has_changeset(custom_changeset)

    assert journal_db.get(b'1') == b'test-a'


def test_custom_snapshot_revert_on_reuse(journal_db):
    custom_changeset = uuid4()
    journal_db.record(custom_changeset)

    auto_changeset = journal_db.record()

    with pytest.raises(ValidationError):
        journal_db.record(custom_changeset)

    with pytest.raises(ValidationError):
        journal_db.record(auto_changeset)


def test_snapshot_and_revert_with_delete(journal_db):
    journal_db.set(b'1', b'test-a')

    assert journal_db.exists(b'1') is True
    assert journal_db.get(b'1') == b'test-a'

    changeset = journal_db.record()

    journal_db.delete(b'1')

    assert journal_db.exists(b'1') is False

    journal_db.discard(changeset)

    assert journal_db.exists(b'1') is True
    assert journal_db.get(b'1') == b'test-a'


def test_snapshot_and_revert_with_clear(journal_db, memory_db):
    memory_db.set(b'only-in-wrapped', b'A')
    memory_db.set(b'wrapped-and-journal', b'B')

    journal_db.set(b'wrapped-and-journal', b'C')
    journal_db.set(b'only-in-journal', b'D')

    changeset = journal_db.record()

    journal_db.clear()

    assert journal_db.exists(b'only-in-wrapped') is False
    with pytest.raises(KeyError):
        journal_db[b'only-in-wrapped']

    assert journal_db.exists(b'wrapped-and-journal') is False
    with pytest.raises(KeyError):
        journal_db[b'wrapped-and-journal']

    assert journal_db.exists(b'only-in-journal') is False
    with pytest.raises(KeyError):
        journal_db[b'only-in-journal']

    journal_db.discard(changeset)

    assert journal_db.exists(b'only-in-wrapped') is True
    assert journal_db[b'only-in-wrapped'] == b'A'

    assert journal_db.exists(b'wrapped-and-journal') is True
    assert journal_db[b'wrapped-and-journal'] == b'C'

    assert journal_db.exists(b'only-in-journal') is True
    assert journal_db[b'only-in-journal'] == b'D'


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

    journal_db.discard(changeset_b)

    assert journal_db.get(b'1') == b'test-c'

    journal_db.delete(b'1')

    assert journal_db.exists(b'1') is False

    journal_db.discard(changeset_a)

    assert journal_db.get(b'1') == b'test-a'


def test_revert_removes_journal_entries(journal_db):

    changeset_a = journal_db.record()  # noqa: F841
    assert journal_db.has_changeset(changeset_a)

    changeset_b = journal_db.record()
    assert journal_db.has_changeset(changeset_a)
    assert journal_db.has_changeset(changeset_b)

    # Forget *latest* changeset and prove it's the only one removed
    journal_db.discard(changeset_b)
    assert journal_db.has_changeset(changeset_a)
    assert not journal_db.has_changeset(changeset_b)

    changeset_b2 = journal_db.record()
    assert journal_db.has_changeset(changeset_a)
    assert journal_db.has_changeset(changeset_b2)

    changeset_c = journal_db.record()
    assert journal_db.has_changeset(changeset_a)
    assert journal_db.has_changeset(changeset_b2)
    assert journal_db.has_changeset(changeset_c)

    changeset_d = journal_db.record()
    assert journal_db.has_changeset(changeset_a)
    assert journal_db.has_changeset(changeset_b2)
    assert journal_db.has_changeset(changeset_c)
    assert journal_db.has_changeset(changeset_d)

    # Forget everything from b2 (inclusive) and what follows
    journal_db.discard(changeset_b2)
    assert journal_db.has_changeset(changeset_a)
    assert not journal_db.has_changeset(changeset_b2)
    assert not journal_db.has_changeset(changeset_c)
    assert not journal_db.has_changeset(changeset_d)


def test_commit_merges_changeset_into_previous(journal_db):

    changeset = journal_db.record()

    journal_db.set(b'1', b'test-a')
    assert journal_db.get(b'1') == b'test-a'

    before_diff = journal_db.diff()
    journal_db.commit(changeset)

    assert journal_db.diff() == before_diff
    assert journal_db.get(b'1') == b'test-a'
    assert journal_db.has_changeset(changeset) is False


def test_journal_db_has_clear(journal_db):
    journal_db.clear()
    assert journal_db.has_clear()

    journal_db.reset()
    assert not journal_db.has_clear()

    journal_db.record()
    journal_db.clear()

    assert journal_db.has_clear()


def test_merged_clear_still_clears_before_merge(journal_db, memory_db):
    memory_db.set(b'only-in-wrapped', b'A')
    memory_db.set(b'wrapped-and-journal', b'B')

    journal_db.set(b'wrapped-and-journal', b'C')
    journal_db.set(b'only-in-journal', b'D')

    journal_db.record()
    journal_db.set(b'in-unmerged-snapshot', b'E')

    journal_db.record()
    journal_db.set(b'in-merged-snapshot', b'F')

    changeset3 = journal_db.record()
    journal_db.set(b'just-before-clear', b'G')
    journal_db.clear()
    journal_db.set(b'just-after-clear', b'H')

    journal_db.commit(changeset3)

    assert not journal_db.exists(b'only-in-wrapped')
    assert not journal_db.exists(b'wrapped-and-journal')
    assert not journal_db.exists(b'only-in-journal')
    assert not journal_db.exists(b'in-merged-snapshot')
    assert not journal_db.exists(b'in-unmerged-snapshot')
    assert not journal_db.exists(b'just-before-clear')
    assert journal_db.exists(b'just-after-clear')


def test_committing_middle_changeset_merges_in_subsequent_changesets(journal_db):

    journal_db.set(b'1', b'test-a')
    changeset_a = journal_db.record()
    assert journal_db.has_changeset(changeset_a)

    journal_db.set(b'1', b'test-b')
    changeset_b = journal_db.record()
    assert journal_db.has_changeset(changeset_a)
    assert journal_db.has_changeset(changeset_b)

    journal_db.set(b'1', b'test-c')
    changeset_c = journal_db.record()
    assert journal_db.has_changeset(changeset_a)
    assert journal_db.has_changeset(changeset_b)
    assert journal_db.has_changeset(changeset_c)

    journal_db.commit(changeset_b)
    assert journal_db.get(b'1') == b'test-c'
    assert journal_db.has_changeset(changeset_a)
    assert journal_db.has_changeset(changeset_b) is False
    assert journal_db.has_changeset(changeset_c) is False


def test_flatten_does_not_persist_0_checkpoints(journal_db, memory_db):
    journal_db.set(b'before-record', b'test-a')

    # should have no effect
    journal_db.flatten()

    assert b'before-record' not in memory_db
    assert b'before-record' in journal_db

    journal_db.persist()

    assert b'before-record' in memory_db


def test_flatten_does_not_persist_1_checkpoint(journal_db, memory_db):
    journal_db.set(b'before-record', b'test-a')

    checkpoint = journal_db.record()

    journal_db.set(b'after-one-record', b'test-b')

    # should only remove this checkpoint, but after-one-record is still available
    assert journal_db.has_changeset(checkpoint)
    journal_db.flatten()
    assert not journal_db.has_changeset(checkpoint)

    assert b'before-record' in journal_db
    assert b'after-one-record' in journal_db

    # changes should not be persisted yet
    assert b'before-record' not in memory_db
    assert b'after-one-record' not in memory_db

    journal_db.persist()

    assert b'before-record' in memory_db
    assert b'after-one-record' in memory_db


def test_flatten_does_not_persist_2_checkpoint(journal_db, memory_db):
    journal_db.set(b'before-record', b'test-a')

    checkpoint1 = journal_db.record()

    journal_db.set(b'after-one-record', b'test-b')

    checkpoint2 = journal_db.record()

    journal_db.set(b'after-two-records', b'3')

    # should remove these checkpoints, but after-one-record & after-two-records are still available
    assert journal_db.has_changeset(checkpoint1)
    assert journal_db.has_changeset(checkpoint2)
    journal_db.flatten()
    assert not journal_db.has_changeset(checkpoint1)
    assert not journal_db.has_changeset(checkpoint2)

    assert b'before-record' in journal_db
    assert b'after-one-record' in journal_db
    assert b'after-two-records' in journal_db

    assert b'before-record' not in memory_db
    assert b'after-one-record' not in memory_db
    assert b'after-two-records' not in memory_db

    journal_db.persist()

    assert b'before-record' in memory_db
    assert b'after-one-record' in memory_db
    assert b'after-two-records' in memory_db


def test_persist_writes_to_underlying_db(journal_db, memory_db):
    changeset = journal_db.record()  # noqa: F841
    journal_db.set(b'1', b'test-a')
    assert journal_db.get(b'1') == b'test-a'
    assert memory_db.exists(b'1') is False

    changeset_b = journal_db.record()  # noqa: F841

    journal_db.set(b'1', b'test-b')
    assert journal_db.get(b'1') == b'test-b'
    assert memory_db.exists(b'1') is False

    journal_db.persist()
    assert not journal_db.has_changeset(changeset)
    assert not journal_db.has_changeset(changeset_b)
    assert memory_db.get(b'1') == b'test-b'


def test_journal_restarts_after_write(journal_db, memory_db):
    journal_db.set(b'1', b'test-a')

    journal_db.persist()

    assert memory_db.get(b'1') == b'test-a'

    journal_db.set(b'1', b'test-b')

    journal_db.persist()

    assert memory_db.get(b'1') == b'test-b'


def test_returns_key_from_underlying_db_if_missing(journal_db, memory_db):
    journal_db.record()
    memory_db.set(b'1', b'test-a')

    assert memory_db.exists(b'1')

    assert journal_db.get(b'1') == b'test-a'


def test_is_empty_if_deleted(journal_db, memory_db):
    memory_db.set(b'1', b'test-a')

    journal_db.record()

    del journal_db[b'1']

    assert not journal_db.exists(b'1')


# keys: a-e, values: A-E
FIXTURE_KEYS = st.one_of([st.just(bytes([byte])) for byte in range(ord('a'), ord('f'))])
FIXTURE_VALUES = st.one_of([st.just(bytes([byte])) for byte in range(ord('A'), ord('F'))])
DO_RECORD = object()


@given(
    st.lists(
        st.one_of(
            FIXTURE_KEYS,  # deletions
            st.tuples(  # updates
                FIXTURE_KEYS,
                FIXTURE_VALUES,
            ),
            st.just(DO_RECORD),
        ),
        max_size=10,
    ),
)
def test_journal_db_diff_application_mimics_persist(journal_db, memory_db, actions):
    memory_db.kv_store.clear()  # hypothesis isn't resetting the other test-scoped fixtures
    for action in actions:
        if action is DO_RECORD:
            journal_db.record()
        elif len(action) == 1:
            try:
                del journal_db[action]
            except KeyError:
                pass
        elif len(action) == 2:
            key, val = action
            journal_db.set(key, val)
        else:
            raise Exception("Incorrectly formatted fixture input: %r" % action)

    assert MemoryDB({}) == memory_db
    diff = journal_db.diff()
    journal_db.persist()

    diff_test_db = MemoryDB()
    diff.apply_to(diff_test_db)

    assert memory_db == diff_test_db


def test_journal_persist_delete_KeyError_then_persist():
    db = {b'delete-me': b'val'}
    memory_db = MemoryDB(db)

    journal_db = JournalDB(memory_db)

    del journal_db[b'delete-me']

    # Let's artificially remove the key so it fails on delete
    # (this might happen if the wrapped db is a trie)
    db.clear()
    with pytest.raises(KeyError):
        journal_db.persist()

    # A persist that fails reinstates all the pending changes as a single changeset
    # Let's add the value to the Memory DB so doesn't fail on delete and try again:
    db[b'delete-me'] = b'val'

    # smoke test that persist works after an exception
    journal_db[b'new-key'] = b'new-val'
    journal_db.persist()
    assert memory_db[b'new-key'] == b'new-val'
    assert b'delete-me' not in memory_db


class MemoryDBSetRaisesKeyError(MemoryDB):
    def __setitem__(self, *args):
        raise KeyError("Artificial key error during set, can happen if underlying db is trie")


def test_journal_persist_set_KeyError():
    memory_db = MemoryDBSetRaisesKeyError()

    # make sure test is set up correctly
    with pytest.raises(KeyError):
        memory_db[b'failing-to-set-key'] = b'val'

    journal_db = JournalDB(memory_db)

    journal_db[b'failing-to-set-key'] = b'val'
    with pytest.raises(KeyError):
        journal_db.persist()


def test_journal_persist_set_KeyError_leaves_changeset_in_place():
    memory_db = MemoryDBSetRaisesKeyError()

    journal_db = JournalDB(memory_db)

    journal_db[b'failing-to-set-key'] = b'val'
    with pytest.raises(KeyError):
        journal_db.persist()

    diff = journal_db.diff()
    assert diff.pending_items() == ((b'failing-to-set-key', b'val'), )


def test_journal_persist_set_KeyError_then_persist():
    original_data = {b'data-to-delete': b'val'}
    memory_db = MemoryDBSetRaisesKeyError(original_data)

    journal_db = JournalDB(memory_db)

    journal_db[b'failing-to-set-key'] = b'val'
    with pytest.raises(KeyError):
        journal_db.persist()
    assert b'failing-to-set-key' not in memory_db

    # A persist that fails reinstates all the pending changes as a single changeset
    # Let's switch to a Memory DB that doesn't fail on delete and try again:
    journal_db._wrapped_db = original_data

    # smoke test that persist works after an exception
    del journal_db[b'data-to-delete']
    journal_db.persist()
    assert b'data-to-delete' not in memory_db
    # This key is set on the second attempt
    assert b'failing-to-set-key' in memory_db


def test_journal_db_diff_respects_clear(journal_db):
    journal_db[b'first'] = b'val'
    journal_db.clear()

    pending = journal_db.diff().pending_items()
    assert len(pending) == 0


def test_journal_db_rejects_committing_root(journal_db):
    root = journal_db._journal.root_changeset_id
    with pytest.raises(ValidationError):
        journal_db.commit(root)


def test_journal_db_commit_missing_changeset(journal_db):
    checkpoint = journal_db.record()
    journal_db.commit(checkpoint)

    # checkpoint doesn't exist anymore
    with pytest.raises(ValidationError):
        journal_db.commit(checkpoint)


def test_journal_db_discard_missing_changeset(journal_db):
    checkpoint = journal_db.record()
    journal_db.discard(checkpoint)

    # checkpoint doesn't exist anymore
    with pytest.raises(ValidationError):
        journal_db.discard(checkpoint)


@pytest.mark.parametrize('do_final_record', (True, False))
def test_journal_db_discard_to_deleted(journal_db, do_final_record):
    journal_db[1] = b'original-value'
    checkpoint_created = journal_db.record()
    del journal_db[1]
    checkpoint_deleted = journal_db.record()
    journal_db[1] = b'value-after-delete'
    if do_final_record:
        journal_db.record()

    assert journal_db[1] == b'value-after-delete'

    journal_db.discard(checkpoint_deleted)
    assert 1 not in journal_db
    with pytest.raises(KeyError):
        journal_db[1]

    journal_db.discard(checkpoint_created)
    assert journal_db[1] == b'original-value'


@pytest.mark.parametrize('do_final_record', (True, False))
def test_journal_db_discard_past_clear(journal_db, do_final_record):
    journal_db[0] = b'untouched-wrapped-value'
    journal_db[1] = b'wrapped-value-to-delete'
    journal_db.persist()

    before_changes = journal_db.record()

    del journal_db[1]
    journal_db[2] = b'fresh-journaled-value-to-delete'
    journal_db.record()

    del journal_db[2]
    checkpoint_before_clear = journal_db.record()

    journal_db[3] = b'added-before-clear'
    journal_db.clear()
    if do_final_record:
        journal_db.record()

    assert 0 not in journal_db
    assert 1 not in journal_db
    assert 2 not in journal_db
    assert 3 not in journal_db

    journal_db.discard(checkpoint_before_clear)

    assert journal_db[0] == b'untouched-wrapped-value'
    assert 1 not in journal_db
    assert 2 not in journal_db
    assert 3 not in journal_db

    journal_db.discard(before_changes)
    assert journal_db[0] == b'untouched-wrapped-value'
    assert journal_db[1] == b'wrapped-value-to-delete'
    assert 2 not in journal_db
    assert 3 not in journal_db
