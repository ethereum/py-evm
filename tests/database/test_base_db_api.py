import pytest
from eth.db.backends.memory import MemoryDB
from eth.db.journal import JournalDB
from eth.db.batch import BatchDB
from eth.db.atomic import AtomicDB
from eth.db.backends.rocks import RocksDB
from eth.db.backends.level import LevelDB


@pytest.fixture(params=[JournalDB, BatchDB, MemoryDB, AtomicDB, LevelDB, RocksDB])
def db(request, tmpdir):
    if request.param is JournalDB:
        return JournalDB(MemoryDB())
    elif request.param is BatchDB:
        return BatchDB(MemoryDB())
    elif request.param is MemoryDB:
        return MemoryDB()
    elif request.param is AtomicDB:
        return AtomicDB(MemoryDB())
    elif request.param is LevelDB:
        return LevelDB(db_path=tmpdir.mkdir("level_db_path"))
    elif request.param is RocksDB:
        return RocksDB(db_path=tmpdir.mkdir("rocks_db_path"))
    else:
        raise Exception("Invariant")


def test_database_api_get(db):
    db[b'key-1'] = b'value-1'

    assert db.get(b'key-1') == b'value-1'
    assert db[b'key-1'] == b'value-1'


def test_database_api_set(db):
    db[b'key-1'] = b'value-1'
    assert db[b'key-1'] == b'value-1'
    db[b'key-1'] = b'value-2'
    assert db[b'key-1'] == b'value-2'

    db.set(b'key-1', b'value-1')
    assert db[b'key-1'] == b'value-1'
    db.set(b'key-1', b'value-2')
    assert db[b'key-1'] == b'value-2'


def test_database_api_existence_checking(db):
    assert not db.exists(b'key-1')
    assert b'key-1' not in db

    db[b'key-1'] = b'value-1'

    assert db.exists(b'key-1')
    assert b'key-1' in db


def test_database_api_delete(db):
    db[b'key-1'] = b'value-1'
    db[b'key-2'] = b'value-2'

    assert db.exists(b'key-1')
    assert db.exists(b'key-2')
    assert b'key-1' in db
    assert b'key-2' in db

    del db[b'key-1']
    db.delete(b'key-2')

    assert not db.exists(b'key-1')
    assert not db.exists(b'key-2')
    assert b'key-1' not in db
    assert b'key-2' not in db


def test_database_api_missing_key_retrieval(db):
    assert db.get(b'does-not-exist') is None

    with pytest.raises(KeyError):
        db[b'does-not-exist']


def test_database_api_keyerror_for_del_on_missing_key(db):
    assert not db.exists(b'does-not-exist')

    with pytest.raises(KeyError):
        del db[b'does-not-exist']


def test_database_api_no_error_for_delete_call_on_missing_key(db):
    assert not db.exists(b'does-not-exist')

    db.delete(b'does-not-exist')
