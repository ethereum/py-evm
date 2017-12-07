import pytest
from evm.db.backends.memory import MemoryDB
from evm.db.tracked import TrackedDB


@pytest.fixture
def tracked_db():
    return TrackedDB(MemoryDB())


def test_set_and_get(tracked_db):
    # set
    tracked_db.set(b'1', b'test')
    tracked_db.set(b'2', b'test')
    assert tracked_db.writes.get(b'1') == b'test'
    assert len(tracked_db.writes) == 2

    # get
    assert tracked_db.get(b'1') == b'test'
    assert tracked_db.get(b'2') == b'test'
    assert tracked_db.reads.get(b'1') == b'test'
    assert len(tracked_db.reads) == 2


def test_exists_and_delete(tracked_db):
    tracked_db.set(b'1', b'test')
    assert tracked_db.writes.get(b'1') == b'test'

    # exists
    tracked_db._reads = {}  # clear _reads
    # existence is True
    assert tracked_db.exists(b'1')
    assert tracked_db.reads.get(b'1') == b'test'
    # existence is False
    assert not tracked_db.exists(b'2')
    assert tracked_db.reads.get(b'2') is None

    # delete
    tracked_db._writes = {}  # clear _writes
    tracked_db.delete(b'1')
    assert b'1' in tracked_db.writes
    assert tracked_db.writes.get(b'1') is None


def test_get_non_existent_value(tracked_db):
    with pytest.raises(KeyError):
        tracked_db.get(b'does-not-exist')
    assert b'does-not-exist' not in tracked_db.reads


def test_delete_non_existent_value(tracked_db):
    with pytest.raises(KeyError):
        tracked_db.delete(b'does-not-exist')
    assert b'does-not-exist' not in tracked_db.writes
