import pytest
from evm.db.backends.memory import MemoryDB
from evm.db.tracked import TrackedDB


@pytest.fixture
def tracked_db():
    return TrackedDB(MemoryDB())


def test_set_and_get(tracked_db):
    tracked_db.set(b'1', b'test')
    assert tracked_db.get_writes(b'1') == b'test'

    assert tracked_db.get(b'1') == b'test'
    assert tracked_db.get_reads(b'1') == b'test'


def test_exists_and_clear_log_and_delete(tracked_db):
    tracked_db.set(b'1', b'test')
    assert tracked_db.get_writes(b'1') == b'test'

    # exists
    assert tracked_db.exists(b'1')

    # clear writes
    assert tracked_db.get_writes(b'1') == b'test'
    tracked_db.clear_log()
    assert tracked_db.get_writes(b'1') is None
    assert not tracked_db.get_writes()
    assert not tracked_db.get_reads()

    # delete
    tracked_db.delete(b'1')
    assert tracked_db.get_writes(b'1') == b'test'


def test_get_non_existent_value(tracked_db):
    with pytest.raises(KeyError):
        tracked_db.get(b'does-not-exist')
    assert b'does-not-exist' not in tracked_db.get_reads()


def test_delete_non_existent_value(tracked_db):
    with pytest.raises(KeyError):
        tracked_db.delete(b'does-not-exist')
    assert b'does-not-exist' not in tracked_db.get_writes()
