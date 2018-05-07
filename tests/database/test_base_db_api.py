import pytest
from evm.db.backends.memory import MemoryDB
from evm.db.journal import JournalDB
from evm.db.batch import BatchDB


@pytest.fixture(params=[JournalDB, BatchDB, MemoryDB])
def db(request):
    base_db = MemoryDB()
    if request.param is JournalDB:
        return JournalDB(base_db)
    elif request.param is BatchDB:
        return BatchDB(base_db)
    elif request.param is MemoryDB:
        return base_db
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


def test_database_api_missing_key_for_deletion(db):
    db.delete(b'does-not-exist')

    with pytest.raises(KeyError):
        del db[b'does-not-exist']
