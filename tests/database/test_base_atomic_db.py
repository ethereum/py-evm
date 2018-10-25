import pytest

from eth_utils import ValidationError

from eth.db.atomic import AtomicDB
from eth.db.backends.level import LevelDB


@pytest.fixture(params=['atomic', 'level'])
def atomic_db(request, tmpdir):
    if request.param == 'atomic':
        return AtomicDB()
    elif request.param == 'level':
        return LevelDB(db_path=tmpdir.mkdir("level_db_path"))
    else:
        raise ValueError("Unexpected database type: {}".format(request.param))


def test_atomic_batch(atomic_db):
    with atomic_db.atomic_batch() as db:
        db.set(b'1', b'2')
        db.set(b'3', b'4')
        assert db.get(b'1') == b'2'

    assert atomic_db.get(b'1') == b'2'
    assert atomic_db.get(b'3') == b'4'


def test_atomic_db_cannot_recursively_batch(atomic_db):
    with atomic_db.atomic_batch() as db:
        with pytest.raises(AttributeError):
            with db.atomic_batch():
                assert False, "LevelDB should not permit recursive batching of changes"


def test_atomic_db_with_set_and_delete_batch(atomic_db):
    atomic_db[b'key-1'] = b'origin'

    with atomic_db.atomic_batch() as db:
        db.delete(b'key-1')

        assert b'key-1' not in db
        with pytest.raises(KeyError):
            assert db[b'key-1']

    with pytest.raises(KeyError):
        atomic_db[b'key-1']


def test_atomic_db_unbatched_sets_are_immediate(atomic_db):
    atomic_db[b'1'] = b'A'

    with atomic_db.atomic_batch() as db:
        # Unbatched changes are immediate, and show up in batch reads
        atomic_db[b'1'] = b'B'
        assert db[b'1'] == b'B'

        db[b'1'] = b'C1'

        # It doesn't matter what changes happen underlying, all reads now
        # show the write applied to the batch db handle
        atomic_db[b'1'] = b'C2'
        assert db[b'1'] == b'C1'

    # the batch write should overwrite any intermediate changes
    assert atomic_db[b'1'] == b'C1'


def test_atomic_db_cannot_use_write_batch_after_context(atomic_db):
    atomic_db[b'1'] = b'A'

    with atomic_db.atomic_batch() as db:
        db[b'1'] = b'B'

    with pytest.raises(ValidationError):
        db[b'1'] = b'C'

    with pytest.raises(ValidationError):
        b'1' in db

    with pytest.raises(ValidationError):
        del db[b'1']

    with pytest.raises(ValidationError):
        assert db[b'1'] == 'C'

    # none of the invalid changes above should change the original db
    assert atomic_db[b'1'] == b'B'


def test_atomic_db_with_reverted_delete_batch(atomic_db):
    class CustomException(Exception):
        pass

    atomic_db[b'key-1'] = b'origin'

    with pytest.raises(CustomException):
        with atomic_db.atomic_batch() as db:
            db.delete(b'key-1')

            assert b'key-1' not in db
            with pytest.raises(KeyError):
                assert db[b'key-1']

            raise CustomException('pretend something went wrong')

    assert atomic_db[b'key-1'] == b'origin'


def test_atomic_db_temporary_state_dropped_across_batches(atomic_db):
    class CustomException(Exception):
        pass

    atomic_db[b'key-1'] = b'origin'

    with pytest.raises(CustomException):
        with atomic_db.atomic_batch() as db:
            db.delete(b'key-1')
            db.set(b'key-2', b'val-2')
            raise CustomException('pretend something went wrong')

    with atomic_db.atomic_batch() as db:
        assert db[b'key-1'] == b'origin'
        assert b'key-2' not in db


def test_atomic_db_with_exception_batch(atomic_db):
    atomic_db.set(b'key-1', b'value-1')

    try:
        with atomic_db.atomic_batch() as db:
            db.set(b'key-1', b'new-value-1')
            db.set(b'key-2', b'value-2')
            raise Exception
    except Exception:
        pass

    assert atomic_db.get(b'key-1') == b'value-1'

    with pytest.raises(KeyError):
        atomic_db[b'key-2']
