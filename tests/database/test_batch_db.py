from eth_utils import (
    ValidationError,
)
import pytest

from eth.db.backends.memory import (
    MemoryDB,
)
from eth.db.batch import (
    BatchDB,
)


@pytest.fixture
def base_db():
    return MemoryDB()


@pytest.fixture
def batch_db(base_db):
    return BatchDB(base_db)


@pytest.fixture
def base2_db():
    return MemoryDB()


def test_batch_db_with_set_and_get(base_db, batch_db):
    with batch_db:
        batch_db.set(b"key-1", b"value-1")
        batch_db.set(b"key-2", b"value-2")
        assert batch_db.get(b"key-1") == b"value-1"
        assert batch_db.get(b"key-2") == b"value-2"

        # keys should not yet be set in base db.
        assert b"key-1" not in base_db
        assert b"key-2" not in base_db

        diff = batch_db.diff()

    assert base_db.get(b"key-1") == b"value-1"
    assert base_db.get(b"key-2") == b"value-2"

    example_db = {b"key-3": b"unrelated"}
    expected_result = {
        b"key-1": b"value-1",
        b"key-2": b"value-2",
        b"key-3": b"unrelated",
    }
    diff.apply_to(example_db)
    assert example_db == expected_result


def test_batch_db_with_set_and_delete(base_db, batch_db):
    base_db[b"key-1"] = b"origin"

    with batch_db:
        batch_db.delete(b"key-1")

        assert b"key-1" not in batch_db
        with pytest.raises(KeyError):
            assert batch_db[b"key-1"]

        # key should still be in base batch_db
        assert b"key-1" in base_db
        assert b"key-1" not in batch_db

        diff = batch_db.diff()

    with pytest.raises(KeyError):
        base_db[b"key-1"]
    with pytest.raises(KeyError):
        batch_db[b"key-1"]

    example_db = {b"key-1": b"origin", b"key-2": b"unrelated"}
    expected_result = {b"key-2": b"unrelated"}
    diff.apply_to(example_db)
    assert example_db == expected_result


def test_batch_db_read_through_should_fail_to_commit_deletes(base_db):
    batch_db = BatchDB(base_db, read_through_deletes=True)

    # When a batch_db is reading through it's deletes, those deletes
    # should never be applied. It's nonsense
    with pytest.raises(ValidationError):
        batch_db.commit(apply_deletes=True)


def test_batch_db_read_through_delete(base_db):
    base_db[b"read-through-deleted"] = b"still-here"

    batch_db = BatchDB(base_db, read_through_deletes=True)

    batch_db.set(b"only-in-batch", b"will-disappear")

    batch_db.delete(b"read-through-deleted")
    batch_db.delete(b"only-in-batch")

    assert b"read-through-deleted" in batch_db
    assert batch_db[b"read-through-deleted"] == b"still-here"

    assert b"only-in-batch" not in batch_db
    with pytest.raises(KeyError):
        batch_db[b"only-in-batch"]

    batch_db.commit(apply_deletes=False)

    assert base_db[b"read-through-deleted"] == b"still-here"

    # deleted batch data should never get pushed to the underlying
    assert b"only-in-batch" not in base_db


def test_batch_db_read_through_delete_after_modify(base_db):
    base_db[b"modify-then-delete"] = b"original"

    batch_db = BatchDB(base_db, read_through_deletes=True)

    batch_db.set(b"modify-then-delete", b"new-val")

    assert batch_db[b"modify-then-delete"] == b"new-val"

    batch_db.delete(b"modify-then-delete")

    assert batch_db[b"modify-then-delete"] == b"original"

    batch_db.commit(apply_deletes=False)

    assert base_db[b"modify-then-delete"] == b"original"


def test_batch_db_with_exception(base_db, batch_db):
    base_db.set(b"key-1", b"value-1")

    try:
        with batch_db:
            batch_db.set(b"key-1", b"new-value-1")
            batch_db.set(b"key-2", b"value-2")
            raise Exception
    except Exception:
        pass

    assert base_db.get(b"key-1") == b"value-1"

    with pytest.raises(KeyError):
        base_db[b"key-2"]
    with pytest.raises(KeyError):
        batch_db[b"key-2"]


def test_batch_db_with_exception_across_contexts(base_db, batch_db):
    base_db[b"key-1"] = b"origin-1"
    base_db[b"key-2"] = b"origin-2"

    try:
        with batch_db:
            batch_db[b"key-1"] = b"value-1"
            raise Exception("throw")
    except Exception:
        pass

    assert base_db[b"key-1"] == b"origin-1"
    assert batch_db[b"key-1"] == b"origin-1"
    assert base_db[b"key-2"] == b"origin-2"
    assert batch_db[b"key-2"] == b"origin-2"

    with batch_db:
        batch_db[b"key-2"] = b"value-2"

    assert base_db[b"key-1"] == b"origin-1"
    assert batch_db[b"key-1"] == b"origin-1"
    assert base_db[b"key-2"] == b"value-2"
    assert batch_db[b"key-2"] == b"value-2"


def test_batch_db_commit_to_new_target(base_db, batch_db, base2_db):
    base_db[b"key-1"] = b"origin-1"
    base_db[b"key-2"] = b"origin-2"

    base2_db[b"key-1"] = b"origin-1"
    base2_db[b"key-2"] = b"origin-2"

    batch_db[b"key-1"] = b"value-1"
    del batch_db[b"key-2"]

    batch_db.commit_to(base2_db, apply_deletes=True)

    # after committing, length of pending changes should be 0
    assert len(batch_db.diff()) == 0

    # changes should be reflected in the target database, not the backing database
    assert base2_db[b"key-1"] == b"value-1"
    assert b"key-2" not in base2_db
    assert base_db[b"key-1"] == b"origin-1"
    assert base_db[b"key-2"] == b"origin-2"


def test_batch_db_commit_to_new_target_without_deletes(base_db, batch_db, base2_db):
    base_db[b"key-2"] = b"origin-2"

    base2_db[b"key-2"] = b"origin-2"

    del batch_db[b"key-2"]

    batch_db.commit_to(base2_db, apply_deletes=False)

    # after committing, length of pending changes should be 0
    assert len(batch_db.diff()) == 0

    # changes should be reflected in the target database, not the backing database
    assert base2_db[b"key-2"] == b"origin-2"
    assert base_db[b"key-2"] == b"origin-2"
