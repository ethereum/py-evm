import pytest

from eth_utils import ValidationError

from eth.db.backends.memory import MemoryDB
from eth.db.atomic import AtomicDB
from eth.db import (
    get_db_backend,
)


pytest.importorskip('leveldb')


# Sets db backend to leveldb
@pytest.fixture
def config_env(monkeypatch):
    monkeypatch.setenv('CHAIN_DB_BACKEND_CLASS',
                       'eth.db.backends.level.LevelDB')


@pytest.fixture
def level_db(config_env, tmpdir):
    level_db_path = str(tmpdir.mkdir("level_db_path"))
    return get_db_backend(db_path=level_db_path)


@pytest.fixture
def memory_db():
    return MemoryDB()


@pytest.fixture
def atomic_db():
    return AtomicDB()


def test_raises_if_db_path_is_not_specified(config_env):
    with pytest.raises(TypeError):
        get_db_backend()


def test_set_and_get(memory_db, level_db):
    level_db.set(b'1', b'1')
    memory_db.set(b'1', b'1')
    assert level_db.get(b'1') == memory_db.get(b'1')


def test_atomic_batch(level_db, atomic_db):
    with level_db.atomic_batch() as db:
        db.set(b'1', b'2')
        db.set(b'3', b'4')
        assert db.get(b'1') == b'2'

    with atomic_db.atomic_batch() as db:
        db.set(b'1', b'2')
        db.set(b'3', b'4')
        assert db.get(b'1') == b'2'

    assert level_db.get(b'1') == atomic_db.get(b'1')
    assert level_db.get(b'3') == atomic_db.get(b'3')


def test_level_db_cannot_recursively_batch(level_db):
    with level_db.atomic_batch() as db:
        with pytest.raises(AttributeError):
            with db.atomic_batch():
                assert False, "LevelDB should not permit recursive batching of changes"


def test_level_db_with_set_and_delete_batch(level_db):
    level_db[b'key-1'] = b'origin'

    with level_db.atomic_batch() as db:
        db.delete(b'key-1')

        assert b'key-1' not in db
        with pytest.raises(KeyError):
            assert db[b'key-1']

    with pytest.raises(KeyError):
        level_db[b'key-1']


def test_level_db_unbatched_sets_are_immediate(level_db):
    level_db[b'1'] = b'A'

    with level_db.atomic_batch() as db:
        # Unbatched changes are immediate, and show up in batch reads
        level_db[b'1'] = b'B'
        assert db[b'1'] == b'B'

        db[b'1'] = b'C1'

        # It doesn't matter what changes happen underlying, all reads now
        # show the write applied to the batch db handle
        level_db[b'1'] = b'C2'
        assert db[b'1'] == b'C1'

    # the batch write should overwrite any intermediate changes
    assert level_db[b'1'] == b'C1'


def test_level_db_cannot_use_write_batch_after_context(level_db):
    level_db[b'1'] = b'A'

    with level_db.atomic_batch() as db:
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
    assert level_db[b'1'] == b'B'


def test_level_db_with_reverted_delete_batch(level_db):
    class CustomException(Exception):
        pass

    level_db[b'key-1'] = b'origin'

    with pytest.raises(CustomException):
        with level_db.atomic_batch() as db:
            db.delete(b'key-1')

            assert b'key-1' not in db
            with pytest.raises(KeyError):
                assert db[b'key-1']

            raise CustomException('pretend something went wrong')

    assert level_db[b'key-1'] == b'origin'


def test_level_db_temporary_state_dropped_across_batches(level_db):
    class CustomException(Exception):
        pass

    level_db[b'key-1'] = b'origin'

    with pytest.raises(CustomException):
        with level_db.atomic_batch() as db:
            db.delete(b'key-1')
            db.set(b'key-2', b'val-2')
            raise CustomException('pretend something went wrong')

    with level_db.atomic_batch() as db:
        assert db[b'key-1'] == b'origin'
        assert b'key-2' not in db


def test_level_db_with_exception_batch(level_db):
    level_db.set(b'key-1', b'value-1')

    try:
        with level_db.atomic_batch() as db:
            db.set(b'key-1', b'new-value-1')
            db.set(b'key-2', b'value-2')
            raise Exception
    except Exception:
        pass

    assert level_db.get(b'key-1') == b'value-1'

    with pytest.raises(KeyError):
        level_db[b'key-2']


def test_set_on_existing_value(level_db, memory_db):
    level_db.set(b'1', b'2')
    level_db.set(b'1', b'3')
    memory_db.set(b'1', b'2')
    memory_db.set(b'1', b'3')
    assert level_db.get(b'1') == memory_db.get(b'1')


def test_exists(level_db, memory_db):
    level_db.set(b'1', b'2')
    memory_db.set(b'1', b'1')
    level_db.exists(b'1') == memory_db.exists(b'1')


def test_delete(level_db, memory_db):
    level_db.set(b'1', b'1')
    memory_db.set(b'1', b'1')
    level_db.delete(b'1')
    memory_db.delete(b'1')
    assert level_db.exists(b'1') == memory_db.exists(b'1')
