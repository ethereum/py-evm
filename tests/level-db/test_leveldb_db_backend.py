import pytest
from evm.db.backends.memory import MemoryDB
from evm.db import (
    get_db_backend,
)


pytest.importorskip('leveldb')


# Sets db backend to leveldb
@pytest.fixture
def config_env(monkeypatch):
    monkeypatch.setenv('CHAIN_DB_BACKEND_CLASS',
                       'evm.db.backends.level.LevelDB')


@pytest.fixture
def level_db(config_env, tmpdir):
    level_db_path = str(tmpdir.mkdir("level_db_path"))
    return get_db_backend(db_path=level_db_path)


@pytest.fixture
def memory_db():
    return MemoryDB()


def test_raises_if_db_path_is_not_specified(config_env):
    with pytest.raises(TypeError):
        get_db_backend()


def test_set_and_get(memory_db, level_db):
    level_db.set(b'1', b'1')
    memory_db.set(b'1', b'1')
    assert level_db.get(b'1') == memory_db.get(b'1')


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


def test_snapshot_and_revert(level_db):
    snapshot = level_db.snapshot()
    level_db.set(b'1', b'1')
    assert level_db.get(b'1')
    with pytest.raises(KeyError):
        snapshot.get(b'1')
    level_db.revert(snapshot)
    with pytest.raises(KeyError):
        level_db.get(b'1')
