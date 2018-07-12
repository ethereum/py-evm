import pytest
from eth.db.backends.memory import MemoryDB
from eth.db.batch import BatchDB


@pytest.fixture
def base_db():
    return MemoryDB()


@pytest.fixture
def batch_db(base_db):
    return BatchDB(base_db)


def test_batch_db_with_set_and_get(base_db, batch_db):
    with batch_db:
        batch_db.set(b'key-1', b'value-1')
        batch_db.set(b'key-2', b'value-2')
        assert batch_db.get(b'key-1') == b'value-1'
        assert batch_db.get(b'key-2') == b'value-2'

        # keys should not yet be set in base db.
        assert b'key-1' not in base_db
        assert b'key-2' not in base_db

        diff = batch_db.diff()

    assert base_db.get(b'key-1') == b'value-1'
    assert base_db.get(b'key-2') == b'value-2'

    example_db = {b'key-3': b'unrelated'}
    expected_result = {b'key-1': b'value-1', b'key-2': b'value-2', b'key-3': b'unrelated'}
    diff.apply_to(example_db)
    assert example_db == expected_result


def test_batch_db_with_set_and_delete(base_db, batch_db):
    base_db[b'key-1'] = b'origin'

    with batch_db:
        batch_db.delete(b'key-1')

        assert b'key-1' not in batch_db
        with pytest.raises(KeyError):
            assert batch_db[b'key-1']

        # key should still be in base batch_db
        assert b'key-1' in base_db
        assert b'key-1' not in batch_db

        diff = batch_db.diff()

    with pytest.raises(KeyError):
        base_db[b'key-1']
    with pytest.raises(KeyError):
        batch_db[b'key-1']

    example_db = {b'key-1': b'origin', b'key-2': b'unrelated'}
    expected_result = {b'key-2': b'unrelated'}
    diff.apply_to(example_db)
    assert example_db == expected_result


def test_batch_db_with_exception(base_db, batch_db):
    base_db.set(b'key-1', b'value-1')

    try:
        with batch_db:
            batch_db.set(b'key-1', b'new-value-1')
            batch_db.set(b'key-2', b'value-2')
            raise Exception
    except Exception:
        pass

    assert base_db.get(b'key-1') == b'value-1'

    with pytest.raises(KeyError):
        base_db[b'key-2']
    with pytest.raises(KeyError):
        batch_db[b'key-2']


def test_batch_db_with_exception_across_contexts(base_db, batch_db):
    base_db[b'key-1'] = b'origin-1'
    base_db[b'key-2'] = b'origin-2'

    try:
        with batch_db:
            batch_db[b'key-1'] = b'value-1'
            raise Exception('throw')
    except Exception:
        pass

    assert base_db[b'key-1'] == b'origin-1'
    assert batch_db[b'key-1'] == b'origin-1'
    assert base_db[b'key-2'] == b'origin-2'
    assert batch_db[b'key-2'] == b'origin-2'

    with batch_db:
        batch_db[b'key-2'] = b'value-2'

    assert base_db[b'key-1'] == b'origin-1'
    assert batch_db[b'key-1'] == b'origin-1'
    assert base_db[b'key-2'] == b'value-2'
    assert batch_db[b'key-2'] == b'value-2'
