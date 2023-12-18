from eth_utils import (
    ValidationError,
)
from hypothesis import (
    given,
    settings,
    strategies as st,
)
from hypothesis.stateful import (
    Bundle,
    RuleBasedStateMachine,
    rule,
)
import pytest

from eth.db.backends.memory import (
    MemoryDB,
)
from eth.db.journal import (
    JournalDB,
)
from eth.db.slow_journal import (
    JournalDB as SlowJournalDB,
)
from eth.vm.interrupt import (
    EVMMissingData,
)


@pytest.fixture
def memory_db():
    return MemoryDB()


@pytest.fixture
def journal_db(memory_db):
    return JournalDB(memory_db)


def test_delete_removes_data_from_underlying_db_after_persist(journal_db, memory_db):
    memory_db.set(b"1", b"test-a")

    assert memory_db.exists(b"1") is True

    journal_db.delete(b"1")
    assert memory_db.exists(b"1") is True
    journal_db.persist()

    assert memory_db.exists(b"1") is False


def test_clear_leaves_data_in_underlying_db_after_persist(journal_db, memory_db):
    """
    JournalDB.clear() can't assume that it can iterate all underlying keys, so it
    can't know which data to delete on disk. Instead, clear() is only responsible
    for deleting all changes that came before it.
    """
    memory_db.set(b"underlying-untouched", b"exists")
    memory_db.set(b"underlying-modified", b"unchanged")

    journal_db.set(b"new-before-clear", b"never added")
    journal_db.set(b"underlying-modified", b"dropped")
    journal_db.clear()
    journal_db.set(b"after-clear", b"added")

    journal_db.persist()

    assert memory_db[b"underlying-untouched"] == b"exists"
    assert memory_db[b"underlying-modified"] == b"unchanged"
    with pytest.raises(KeyError):
        memory_db[b"new-before-clear"]
    assert memory_db[b"after-clear"] == b"added"


def test_snapshot_and_revert_with_set(journal_db):
    journal_db.set(b"1", b"test-a")

    assert journal_db.get(b"1") == b"test-a"

    checkpoint = journal_db.record()

    journal_db.set(b"1", b"test-b")

    assert journal_db.get(b"1") == b"test-b"

    journal_db.discard(checkpoint)

    assert journal_db.get(b"1") == b"test-a"


def test_custom_snapshot_and_revert_with_set(journal_db):
    journal_db.set(b"1", b"test-a")

    assert journal_db.get(b"1") == b"test-a"

    custom_checkpoint = -1
    checkpoint = journal_db.record(custom_checkpoint)

    assert journal_db.has_checkpoint(custom_checkpoint)
    assert checkpoint == custom_checkpoint

    journal_db.set(b"1", b"test-b")

    assert journal_db.get(b"1") == b"test-b"

    journal_db.discard(checkpoint)

    assert not journal_db.has_checkpoint(custom_checkpoint)

    assert journal_db.get(b"1") == b"test-a"


def test_custom_snapshot_revert_on_reuse(journal_db):
    custom_checkpoint = -1
    journal_db.record(custom_checkpoint)

    auto_checkpoint = journal_db.record()

    with pytest.raises(ValidationError):
        journal_db.record(custom_checkpoint)

    with pytest.raises(ValidationError):
        journal_db.record(auto_checkpoint)


def test_snapshot_and_revert_with_delete(journal_db):
    journal_db.set(b"1", b"test-a")

    assert journal_db.exists(b"1") is True
    assert journal_db.get(b"1") == b"test-a"

    checkpoint = journal_db.record()

    journal_db.delete(b"1")

    assert journal_db.exists(b"1") is False

    journal_db.discard(checkpoint)

    assert journal_db.exists(b"1") is True
    assert journal_db.get(b"1") == b"test-a"


def test_snapshot_and_revert_with_clear(journal_db, memory_db):
    memory_db.set(b"only-in-wrapped", b"A")
    memory_db.set(b"wrapped-and-journal", b"B")

    journal_db.set(b"wrapped-and-journal", b"C")
    journal_db.set(b"only-in-journal", b"D")

    checkpoint = journal_db.record()

    journal_db.clear()

    assert journal_db.exists(b"only-in-wrapped") is False
    with pytest.raises(KeyError):
        journal_db[b"only-in-wrapped"]

    assert journal_db.exists(b"wrapped-and-journal") is False
    with pytest.raises(KeyError):
        journal_db[b"wrapped-and-journal"]

    assert journal_db.exists(b"only-in-journal") is False
    with pytest.raises(KeyError):
        journal_db[b"only-in-journal"]

    journal_db.discard(checkpoint)

    assert journal_db.exists(b"only-in-wrapped") is True
    assert journal_db[b"only-in-wrapped"] == b"A"

    assert journal_db.exists(b"wrapped-and-journal") is True
    assert journal_db[b"wrapped-and-journal"] == b"C"

    assert journal_db.exists(b"only-in-journal") is True
    assert journal_db[b"only-in-journal"] == b"D"


def test_revert_clears_reverted_journal_entries(journal_db):
    journal_db.set(b"1", b"test-a")

    assert journal_db.get(b"1") == b"test-a"

    checkpoint_a = journal_db.record()

    journal_db.set(b"1", b"test-b")
    journal_db.delete(b"1")
    journal_db.set(b"1", b"test-c")

    assert journal_db.get(b"1") == b"test-c"

    checkpoint_b = journal_db.record()

    journal_db.set(b"1", b"test-d")
    journal_db.delete(b"1")
    journal_db.set(b"1", b"test-e")

    assert journal_db.get(b"1") == b"test-e"

    journal_db.discard(checkpoint_b)

    assert journal_db.get(b"1") == b"test-c"

    journal_db.delete(b"1")

    assert journal_db.exists(b"1") is False

    journal_db.discard(checkpoint_a)

    assert journal_db.get(b"1") == b"test-a"


def test_revert_removes_journal_entries(journal_db):
    checkpoint_a = journal_db.record()
    assert journal_db.has_checkpoint(checkpoint_a)

    checkpoint_b = journal_db.record()
    assert journal_db.has_checkpoint(checkpoint_a)
    assert journal_db.has_checkpoint(checkpoint_b)

    # Forget *latest* checkpoint and prove it's the only one removed
    journal_db.discard(checkpoint_b)
    assert journal_db.has_checkpoint(checkpoint_a)
    assert not journal_db.has_checkpoint(checkpoint_b)

    checkpoint_b2 = journal_db.record()
    assert journal_db.has_checkpoint(checkpoint_a)
    assert journal_db.has_checkpoint(checkpoint_b2)

    checkpoint_c = journal_db.record()
    assert journal_db.has_checkpoint(checkpoint_a)
    assert journal_db.has_checkpoint(checkpoint_b2)
    assert journal_db.has_checkpoint(checkpoint_c)

    checkpoint_d = journal_db.record()
    assert journal_db.has_checkpoint(checkpoint_a)
    assert journal_db.has_checkpoint(checkpoint_b2)
    assert journal_db.has_checkpoint(checkpoint_c)
    assert journal_db.has_checkpoint(checkpoint_d)

    # Forget everything from b2 (inclusive) and what follows
    journal_db.discard(checkpoint_b2)
    assert journal_db.has_checkpoint(checkpoint_a)
    assert not journal_db.has_checkpoint(checkpoint_b2)
    assert not journal_db.has_checkpoint(checkpoint_c)
    assert not journal_db.has_checkpoint(checkpoint_d)


def test_commit_merges_checkpoint_into_previous(journal_db):
    checkpoint = journal_db.record()

    journal_db.set(b"1", b"test-a")
    assert journal_db.get(b"1") == b"test-a"

    before_diff = journal_db.diff()
    journal_db.commit(checkpoint)

    assert journal_db.diff() == before_diff
    assert journal_db.get(b"1") == b"test-a"
    assert journal_db.has_checkpoint(checkpoint) is False


def test_journal_db_has_clear(journal_db):
    journal_db.clear()
    assert journal_db.has_clear()

    journal_db.reset()
    assert not journal_db.has_clear()

    journal_db.record()
    journal_db.clear()

    assert journal_db.has_clear()


def test_merged_clear_still_clears_before_merge(journal_db, memory_db):
    memory_db.set(b"only-in-wrapped", b"A")
    memory_db.set(b"wrapped-and-journal", b"B")

    journal_db.set(b"wrapped-and-journal", b"C")
    journal_db.set(b"only-in-journal", b"D")

    journal_db.record()
    journal_db.set(b"in-unmerged-snapshot", b"E")

    journal_db.record()
    journal_db.set(b"in-merged-snapshot", b"F")

    checkpoint3 = journal_db.record()
    journal_db.set(b"just-before-clear", b"G")
    journal_db.clear()
    journal_db.set(b"just-after-clear", b"H")

    journal_db.commit(checkpoint3)

    assert not journal_db.exists(b"only-in-wrapped")
    assert not journal_db.exists(b"wrapped-and-journal")
    assert not journal_db.exists(b"only-in-journal")
    assert not journal_db.exists(b"in-merged-snapshot")
    assert not journal_db.exists(b"in-unmerged-snapshot")
    assert not journal_db.exists(b"just-before-clear")
    assert journal_db.exists(b"just-after-clear")


def test_committing_middle_checkpoint_includes_subsequent_checkpoints(journal_db):
    journal_db.set(b"1", b"test-a")
    checkpoint_a = journal_db.record()
    assert journal_db.has_checkpoint(checkpoint_a)

    journal_db.set(b"1", b"test-b")
    checkpoint_b = journal_db.record()
    assert journal_db.has_checkpoint(checkpoint_a)
    assert journal_db.has_checkpoint(checkpoint_b)

    journal_db.set(b"1", b"test-c")
    checkpoint_c = journal_db.record()
    assert journal_db.has_checkpoint(checkpoint_a)
    assert journal_db.has_checkpoint(checkpoint_b)
    assert journal_db.has_checkpoint(checkpoint_c)

    journal_db.commit(checkpoint_b)
    assert journal_db.get(b"1") == b"test-c"
    assert journal_db.has_checkpoint(checkpoint_a)
    assert journal_db.has_checkpoint(checkpoint_b) is False
    assert journal_db.has_checkpoint(checkpoint_c) is False


def test_flatten_does_not_persist_0_checkpoints(journal_db, memory_db):
    journal_db.set(b"before-record", b"test-a")

    # should have no effect
    journal_db.flatten()

    assert b"before-record" not in memory_db
    assert b"before-record" in journal_db

    journal_db.persist()

    assert b"before-record" in memory_db


def test_flatten_does_not_persist_1_checkpoint(journal_db, memory_db):
    journal_db.set(b"before-record", b"test-a")

    checkpoint = journal_db.record()

    journal_db.set(b"after-one-record", b"test-b")

    # should only remove this checkpoint, but after-one-record is still available
    assert journal_db.has_checkpoint(checkpoint)
    journal_db.flatten()
    assert not journal_db.has_checkpoint(checkpoint)

    assert b"before-record" in journal_db
    assert b"after-one-record" in journal_db

    # changes should not be persisted yet
    assert b"before-record" not in memory_db
    assert b"after-one-record" not in memory_db

    journal_db.persist()

    assert b"before-record" in memory_db
    assert b"after-one-record" in memory_db


def test_flatten_does_not_persist_2_checkpoint(journal_db, memory_db):
    journal_db.set(b"before-record", b"test-a")

    checkpoint1 = journal_db.record()

    journal_db.set(b"after-one-record", b"test-b")

    checkpoint2 = journal_db.record()

    journal_db.set(b"after-two-records", b"3")

    # should remove these checkpoints, but after-one-record & after-two-records are
    # still available
    assert journal_db.has_checkpoint(checkpoint1)
    assert journal_db.has_checkpoint(checkpoint2)
    journal_db.flatten()
    assert not journal_db.has_checkpoint(checkpoint1)
    assert not journal_db.has_checkpoint(checkpoint2)

    assert b"before-record" in journal_db
    assert b"after-one-record" in journal_db
    assert b"after-two-records" in journal_db

    assert b"before-record" not in memory_db
    assert b"after-one-record" not in memory_db
    assert b"after-two-records" not in memory_db

    journal_db.persist()

    assert b"before-record" in memory_db
    assert b"after-one-record" in memory_db
    assert b"after-two-records" in memory_db


def test_persist_writes_to_underlying_db(journal_db, memory_db):
    checkpoint = journal_db.record()  # noqa: F841
    journal_db.set(b"1", b"test-a")
    assert journal_db.get(b"1") == b"test-a"
    assert memory_db.exists(b"1") is False

    checkpoint_b = journal_db.record()  # noqa: F841

    journal_db.set(b"1", b"test-b")
    assert journal_db.get(b"1") == b"test-b"
    assert memory_db.exists(b"1") is False

    journal_db.persist()
    assert not journal_db.has_checkpoint(checkpoint)
    assert not journal_db.has_checkpoint(checkpoint_b)
    assert memory_db.get(b"1") == b"test-b"


def test_journal_restarts_after_write(journal_db, memory_db):
    journal_db.set(b"1", b"test-a")

    journal_db.persist()

    assert memory_db.get(b"1") == b"test-a"

    journal_db.set(b"1", b"test-b")

    journal_db.persist()

    assert memory_db.get(b"1") == b"test-b"


def test_returns_key_from_underlying_db_if_missing(journal_db, memory_db):
    journal_db.record()
    memory_db.set(b"1", b"test-a")

    assert memory_db.exists(b"1")

    assert journal_db.get(b"1") == b"test-a"


def test_is_empty_if_deleted(journal_db, memory_db):
    memory_db.set(b"1", b"test-a")

    journal_db.record()

    del journal_db[b"1"]

    assert not journal_db.exists(b"1")


# keys: a-e, values: A-E
FIXTURE_KEYS = st.one_of([st.just(bytes([byte])) for byte in range(ord("a"), ord("f"))])
FIXTURE_VALUES = st.one_of(
    [st.just(bytes([byte])) for byte in range(ord("A"), ord("F"))]
)
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
    memory_db.kv_store.clear()  # hypothesis not resetting other test-scoped fixtures
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
            raise Exception(f"Incorrectly formatted fixture input: {repr(action)}")

    assert MemoryDB({}) == memory_db
    diff = journal_db.diff()
    journal_db.persist()

    diff_test_db = MemoryDB()
    diff.apply_to(diff_test_db)

    assert memory_db == diff_test_db


def test_journal_persist_delete_fail_then_persist():
    db = {b"delete-me": b"val"}

    journal_db = JournalDB(db)

    del journal_db[b"delete-me"]

    # Let's artificially remove the key so it fails on delete
    # (this might happen if the wrapped db is a trie)
    db.clear()
    with pytest.raises(KeyError):
        journal_db.persist()

    # A persist that fails reinstates all the pending changes,
    # but without any checkpoints. Let's add the value to the Memory DB so doesn't
    # fail on delete and try again:
    db[b"delete-me"] = b"val"

    # smoke test that persist works after an exception
    journal_db[b"new-key"] = b"new-val"
    journal_db.persist()
    assert db[b"new-key"] == b"new-val"
    assert b"delete-me" not in db


class MemoryDBSetRaisesKeyError(MemoryDB):
    def __setitem__(self, *args):
        raise KeyError(
            "Artificial key error during set, can happen if underlying db is trie"
        )


class MemoryDBSetRaisesMissingData(MemoryDB):
    def __setitem__(self, *args):
        raise EVMMissingData()


@pytest.mark.parametrize(
    "db_class, expected_exception",
    (
        (MemoryDBSetRaisesKeyError, KeyError),
        (MemoryDBSetRaisesMissingData, EVMMissingData),
    ),
)
def test_journal_persist_set_fail(db_class, expected_exception):
    memory_db = db_class()

    # make sure test is set up correctly
    with pytest.raises(expected_exception):
        memory_db[b"failing-to-set-key"] = b"val"

    journal_db = JournalDB(memory_db)

    journal_db[b"failing-to-set-key"] = b"val"

    with pytest.raises(expected_exception):
        journal_db.persist()


@pytest.mark.parametrize(
    "db_class, expected_exception",
    (
        (MemoryDBSetRaisesKeyError, KeyError),
        (MemoryDBSetRaisesMissingData, EVMMissingData),
    ),
)
def test_journal_persist_set_fail_leaves_checkpoint_in_place(
    db_class, expected_exception
):
    memory_db = db_class()

    journal_db = JournalDB(memory_db)

    journal_db[b"failing-to-set-key"] = b"val"
    with pytest.raises(expected_exception):
        journal_db.persist()

    diff = journal_db.diff()
    assert diff.pending_items() == ((b"failing-to-set-key", b"val"),)


@pytest.mark.parametrize(
    "db_class, expected_exception",
    (
        (MemoryDBSetRaisesKeyError, KeyError),
        (MemoryDBSetRaisesMissingData, EVMMissingData),
    ),
)
def test_journal_persist_set_fail_then_persist(db_class, expected_exception):
    original_data = {b"data-to-delete": b"val"}
    memory_db = db_class(original_data)

    journal_db = JournalDB(memory_db)

    journal_db[b"failing-to-set-key"] = b"val"
    with pytest.raises(expected_exception):
        journal_db.persist()
    assert b"failing-to-set-key" not in memory_db

    # A persist that fails reinstates all the pending changes, but with no checkpoints.
    # Let's switch to a Memory DB that doesn't fail on delete and try again:
    journal_db._wrapped_db = original_data

    # smoke test that persist works after an exception
    del journal_db[b"data-to-delete"]
    journal_db.persist()
    assert b"data-to-delete" not in memory_db
    # This key is set on the second attempt
    assert b"failing-to-set-key" in memory_db


def test_journal_db_diff_respects_clear(journal_db):
    journal_db[b"first"] = b"val"
    journal_db.clear()

    pending = journal_db.diff().pending_items()
    assert len(pending) == 0


def test_journal_db_rejects_committing_root(journal_db):
    root = journal_db._journal.root_checkpoint
    with pytest.raises(ValidationError):
        journal_db.commit(root)


def test_journal_db_commit_missing_checkpoint(journal_db):
    checkpoint = journal_db.record()
    journal_db.commit(checkpoint)

    # checkpoint doesn't exist anymore
    with pytest.raises(ValidationError):
        journal_db.commit(checkpoint)


def test_journal_db_discard_missing_checkpoint(journal_db):
    checkpoint = journal_db.record()
    journal_db.discard(checkpoint)

    # checkpoint doesn't exist anymore
    with pytest.raises(ValidationError):
        journal_db.discard(checkpoint)


@pytest.mark.parametrize("do_final_record", (True, False))
def test_journal_db_discard_to_deleted(journal_db, do_final_record):
    journal_db[1] = b"original-value"
    checkpoint_created = journal_db.record()
    del journal_db[1]
    checkpoint_deleted = journal_db.record()
    journal_db[1] = b"value-after-delete"
    if do_final_record:
        journal_db.record()

    assert journal_db[1] == b"value-after-delete"

    journal_db.discard(checkpoint_deleted)
    assert 1 not in journal_db
    with pytest.raises(KeyError):
        journal_db[1]

    journal_db.discard(checkpoint_created)
    assert journal_db[1] == b"original-value"


@pytest.mark.parametrize("do_final_record", (True, False))
def test_journal_db_discard_past_clear(journal_db, do_final_record):
    journal_db[0] = b"untouched-wrapped-value"
    journal_db[1] = b"wrapped-value-to-delete"
    journal_db.persist()

    before_changes = journal_db.record()

    del journal_db[1]
    journal_db[2] = b"fresh-journaled-value-to-delete"
    journal_db.record()

    del journal_db[2]
    checkpoint_before_clear = journal_db.record()

    journal_db[3] = b"added-before-clear"
    journal_db.clear()
    if do_final_record:
        journal_db.record()

    assert 0 not in journal_db
    assert 1 not in journal_db
    assert 2 not in journal_db
    assert 3 not in journal_db

    journal_db.discard(checkpoint_before_clear)

    assert journal_db[0] == b"untouched-wrapped-value"
    assert 1 not in journal_db
    assert 2 not in journal_db
    assert 3 not in journal_db

    journal_db.discard(before_changes)
    assert journal_db[0] == b"untouched-wrapped-value"
    assert journal_db[1] == b"wrapped-value-to-delete"
    assert 2 not in journal_db
    assert 3 not in journal_db


def test_journal_db_commit_then_discard(journal_db):
    discard_to = journal_db.record()
    commit_to = journal_db.record()
    journal_db[1] = b"to-be-removed"

    journal_db.commit(commit_to)
    assert journal_db[1] == b"to-be-removed"

    journal_db.discard(discard_to)
    assert 1 not in journal_db


class JournalComparison(RuleBasedStateMachine):
    """
    Compare an older version of JournalDB against a newer, optimized one.
    """

    def __init__(self):
        super().__init__()
        self.slow_wrapped = {}
        self.slow_journal = SlowJournalDB(self.slow_wrapped)
        self.fast_wrapped = {}
        self.fast_journal = JournalDB(self.fast_wrapped)

    keys = Bundle("keys")
    values = Bundle("values")
    checkpoints = Bundle("checkpoints")

    @rule(target=keys, k=st.binary())
    def add_key(self, k):
        return k

    @rule(target=values, v=st.binary())
    def add_value(self, v):
        return v

    @rule(target=checkpoints)
    def record(self):
        slow_checkpoint = self.slow_journal.record()
        fast_checkpoint = self.fast_journal.record()
        assert self.slow_journal.diff() == self.fast_journal.diff()
        return slow_checkpoint, fast_checkpoint

    @rule(k=keys, v=values)
    def set(self, k, v):
        self.slow_journal[k] = v
        self.fast_journal[k] = v
        assert self.slow_journal.diff() == self.fast_journal.diff()

    @rule(k=keys)
    def delete(self, k):
        if k not in self.slow_journal:
            assert k not in self.fast_journal
            return
        else:
            del self.slow_journal[k]
            del self.fast_journal[k]
            assert self.slow_journal.diff() == self.fast_journal.diff()

    @rule(c=checkpoints)
    def commit(self, c):
        slow_checkpoint, fast_checkpoint = c
        if not self.slow_journal.has_changeset(slow_checkpoint):
            assert not self.fast_journal.has_checkpoint(fast_checkpoint)
            return
        else:
            self.slow_journal.commit(slow_checkpoint)
            self.fast_journal.commit(fast_checkpoint)
            assert self.slow_journal.diff() == self.fast_journal.diff()

    @rule(c=checkpoints)
    def discard(self, c):
        slow_checkpoint, fast_checkpoint = c
        if not self.slow_journal.has_changeset(slow_checkpoint):
            assert not self.fast_journal.has_checkpoint(fast_checkpoint)
        else:
            self.slow_journal.discard(slow_checkpoint)
            self.fast_journal.discard(fast_checkpoint)
            assert self.slow_journal.diff() == self.fast_journal.diff()

    @rule()
    def flatten(self):
        self.slow_journal.flatten()
        self.fast_journal.flatten()
        assert self.slow_journal.diff() == self.fast_journal.diff()

    @rule()
    def persist(self):
        self.slow_journal.persist()
        self.fast_journal.persist()
        assert self.slow_wrapped == self.fast_wrapped


JournalComparison.TestCase.settings = settings(
    max_examples=200, stateful_step_count=100
)
TestJournalComparison = JournalComparison.TestCase
