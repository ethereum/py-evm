import pytest
from evm.db.backends.memory import (
    MemoryDB,
)
from evm.db.batch import (
    BatchDB,
)


def test_set_and_get_permanence():
    with BatchDB(MemoryDB) as batch_db:
        batch_db.set(b'1', b'test')
    assert batch_db.get(b'1') == b'test'


def test_rollback_internal_error():
    with pytest.raises(KeyError):
        with BatchDB(MemoryDB) as batch_db:
            batch_db.set(b'1', b'test')
            batch_db.get(b'does-not-exist')
    assert batch_db.exists(b'1') is False


def test_rollback_external_error():
    with pytest.raises(AssertionError):
        with BatchDB(MemoryDB) as batch_db:
            batch_db.set(b'1', b'test')
            assert False
    assert batch_db.exists(b'1') is False


def test_set_and_get():
    with BatchDB(MemoryDB) as batch_db:
        batch_db.set(b'1', b'test')
        assert batch_db.get(b'1') == b'test'
    assert batch_db.get(b'1') == b'test'


def test_get_non_existent_value():
    with pytest.raises(KeyError):
        with BatchDB(MemoryDB) as batch_db:
            batch_db.get(b'does-not-exist')
    with pytest.raises(KeyError):
        batch_db.get(b'does-not-exist')


def test_delete_non_existent_value():
    with pytest.raises(KeyError):
        with BatchDB(MemoryDB) as batch_db:
            batch_db.delete(b'does-not-exist')
    with pytest.raises(KeyError):
        batch_db.delete(b'does-not-exist')


def test_snapshot_and_revert_with_set():
    with BatchDB(MemoryDB) as batch_db:
        batch_db.set(b'1', b'test-a')

        assert batch_db.get(b'1') == b'test-a'

        snapshot = batch_db.snapshot()

        batch_db.set(b'1', b'test-b')

        assert batch_db.get(b'1') == b'test-b'

        batch_db.revert(snapshot)

        assert batch_db.get(b'1') == b'test-a'
    assert batch_db.get(b'1') == b'test-a'


def test_snapshot_and_revert_with_delete():
    with BatchDB(MemoryDB) as batch_db:
        batch_db.set(b'1', b'test-a')

        assert batch_db.exists(b'1') is True
        assert batch_db.get(b'1') == b'test-a'

        snapshot = batch_db.snapshot()

        batch_db.delete(b'1')

        assert batch_db.exists(b'1') is False

        batch_db.revert(snapshot)

        assert batch_db.exists(b'1') is True
        assert batch_db.get(b'1') == b'test-a'
    assert batch_db.exists(b'1') is True
    assert batch_db.get(b'1') == b'test-a'


def test_revert_clears_reverted_journal_entries():
    with BatchDB(MemoryDB) as batch_db:
        batch_db.set(b'1', b'test-a')

        assert batch_db.get(b'1') == b'test-a'

        snapshot_a = batch_db.snapshot()

        batch_db.set(b'1', b'test-b')
        batch_db.delete(b'1')
        batch_db.set(b'1', b'test-c')

        assert batch_db.get(b'1') == b'test-c'

        snapshot_b = batch_db.snapshot()

        batch_db.set(b'1', b'test-d')
        batch_db.delete(b'1')
        batch_db.set(b'1', b'test-e')

        assert batch_db.get(b'1') == b'test-e'

        batch_db.revert(snapshot_b)

        assert batch_db.get(b'1') == b'test-c'

        batch_db.delete(b'1')

        assert batch_db.exists(b'1') is False

        batch_db.revert(snapshot_a)

        assert batch_db.get(b'1') == b'test-a'
    assert batch_db.get(b'1') == b'test-a'
