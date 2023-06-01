import pytest

from eth.db import (
    get_db_backend,
)
from eth.db.atomic import (
    AtomicDB,
)
from eth.db.backends.memory import (
    MemoryDB,
)

pytest.importorskip("leveldb")


# Sets db backend to leveldb
@pytest.fixture
def config_env(monkeypatch):
    monkeypatch.setenv("CHAIN_DB_BACKEND_CLASS", "eth.db.backends.level.LevelDB")


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
    level_db.set(b"1", b"1")
    memory_db.set(b"1", b"1")
    assert level_db.get(b"1") == memory_db.get(b"1")


def test_set_on_existing_value(level_db, memory_db):
    level_db.set(b"1", b"2")
    level_db.set(b"1", b"3")
    memory_db.set(b"1", b"2")
    memory_db.set(b"1", b"3")
    assert level_db.get(b"1") == memory_db.get(b"1")


def test_exists(level_db, memory_db):
    level_db.set(b"1", b"2")
    memory_db.set(b"1", b"1")
    assert level_db.exists(b"1") == memory_db.exists(b"1")


def test_delete(level_db, memory_db):
    level_db.set(b"1", b"1")
    memory_db.set(b"1", b"1")
    level_db.delete(b"1")
    memory_db.delete(b"1")
    assert level_db.exists(b"1") == memory_db.exists(b"1")
