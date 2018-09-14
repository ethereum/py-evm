import pytest

from eth_utils import ValidationError

from eth.db.atomic import AtomicDB


@pytest.fixture
def atomic_db(base_db):
    return AtomicDB(base_db)


def test_atomic_db_with_set_and_get(base_db, atomic_db):
    with atomic_db.atomic_batch():
        atomic_db.set(b'key-1', b'value-1')
        atomic_db.set(b'key-2', b'value-2')
        assert atomic_db.get(b'key-1') == b'value-1'
        assert atomic_db.get(b'key-2') == b'value-2'

        # keys should not yet be set in base db.
        assert b'key-1' not in base_db
        assert b'key-2' not in base_db

    assert base_db.get(b'key-1') == b'value-1'
    assert base_db.get(b'key-2') == b'value-2'


def test_atomic_db_with_set_and_get_unbatched(base_db, atomic_db):
    atomic_db.set(b'key-1', b'value-1')
    assert atomic_db.get(b'key-1') == b'value-1'
    atomic_db.set(b'key-2', b'value-2')
    assert atomic_db.get(b'key-2') == b'value-2'

    # keys should be immediately set in base db.
    assert base_db.get(b'key-1') == b'value-1'
    assert base_db.get(b'key-2') == b'value-2'


def test_atomic_db_cannot_recursively_batch(base_db, atomic_db):
    with atomic_db.atomic_batch():
        with pytest.raises(ValidationError):
            with atomic_db.atomic_batch():
                assert False, "AtomicDB should not permit recursive batching of changes"


def test_atomic_db_with_set_and_delete(base_db, atomic_db):
    base_db[b'key-1'] = b'origin'

    with atomic_db.atomic_batch():
        atomic_db.delete(b'key-1')

        assert b'key-1' not in atomic_db
        with pytest.raises(KeyError):
            assert atomic_db[b'key-1']

        # key should still be in base atomic_db
        assert b'key-1' in base_db
        assert b'key-1' not in atomic_db

    with pytest.raises(KeyError):
        base_db[b'key-1']
    with pytest.raises(KeyError):
        atomic_db[b'key-1']


def test_atomic_db_with_set_and_delete_unbatched(base_db, atomic_db):
    base_db[b'key-1'] = b'origin'

    atomic_db.delete(b'key-1')

    assert b'key-1' not in atomic_db
    with pytest.raises(KeyError):
        assert atomic_db[b'key-1']

    # key should be immediately removed from base atomic_db
    with pytest.raises(KeyError):
        base_db[b'key-1']


def test_atomic_db_with_exception(base_db, atomic_db):
    base_db.set(b'key-1', b'value-1')

    try:
        with atomic_db.atomic_batch():
            atomic_db.set(b'key-1', b'new-value-1')
            atomic_db.set(b'key-2', b'value-2')
            raise Exception
    except Exception:
        pass

    assert base_db.get(b'key-1') == b'value-1'

    with pytest.raises(KeyError):
        base_db[b'key-2']
    with pytest.raises(KeyError):
        atomic_db[b'key-2']


def test_atomic_db_with_exception_across_contexts(base_db, atomic_db):
    base_db[b'key-1'] = b'origin-1'
    base_db[b'key-2'] = b'origin-2'

    try:
        with atomic_db.atomic_batch():
            atomic_db[b'key-1'] = b'value-1'
            raise Exception('throw')
    except Exception:
        pass

    assert base_db[b'key-1'] == b'origin-1'
    assert atomic_db[b'key-1'] == b'origin-1'
    assert base_db[b'key-2'] == b'origin-2'
    assert atomic_db[b'key-2'] == b'origin-2'

    with atomic_db.atomic_batch():
        atomic_db[b'key-2'] = b'value-2'

    assert base_db[b'key-1'] == b'origin-1'
    assert atomic_db[b'key-1'] == b'origin-1'
    assert base_db[b'key-2'] == b'value-2'
    assert atomic_db[b'key-2'] == b'value-2'
