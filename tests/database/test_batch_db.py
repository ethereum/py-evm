import pytest
from evm.db.backends.memory import MemoryDB
from evm.db.batch import BatchDB


@pytest.fixture
def batch_db():
    return BatchDB(MemoryDB())


def test_set_and_get(batch_db):
    batch_db.set(b'1', b'test')
    assert batch_db.get(b'1') == b'test'


def test_with_set_and_get():
    with BatchDB(MemoryDB()) as db:
        db.set(b'1', b'test1')
        db.set(b'2', b'test2')
        assert db.get(b'1') == b'test1'
        assert db.get(b'2') == b'test2'
    assert db.get(b'1') == b'test1'
    assert db.get(b'2') == b'test2'


def test_with_set_and_delete():
    with BatchDB(MemoryDB()) as db:
        db.set(b'1', b'test1')
        db.set(b'2', b'test2')
        db.delete(b'1')
        assert db.get(b'1') is None
    assert db.get(b'1') is None
    assert db.get(b'2') == b'test2'


def test_batch_update_with_error():
    with BatchDB(MemoryDB()) as db:
        db.set(b'1', b'test1')
        db.set(b'2', b'test2')
        raise IOError
    assert db.get(b'1') is None
    assert db.get(b'2') is None


def test_exists():
    with BatchDB(MemoryDB()) as db:
        db.set(b'1', b'test1')
        db.exists('1')
        db.set(b'2', b'test2')
        db.exists('2')
