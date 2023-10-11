import os
import pytest

from eth.db.backends.memory import (
    MemoryDB,
)
from eth.db.backends.sqlite import (
    SQLiteDB,
)


@pytest.fixture
def sqlite_db(tmpdir):
    # create a temporary database
    db_path = os.path.join(tmpdir, "test.db")
    db = SQLiteDB(db_path)
    yield db
    db.close()


@pytest.fixture
def memory_db(request):
    db = MemoryDB()
    yield db


def test_set_and_get(sqlite_db, memory_db):
    sqlite_db[b"1"] = b"1"
    memory_db[b"1"] = b"1"
    assert sqlite_db[b"1"] == memory_db[b"1"] == b"1"

    sqlite_db.set(b"2", b"2")
    memory_db.set(b"2", b"2")
    assert sqlite_db.get(b"2") == memory_db.get(b"2") == b"2"


def test_set_on_existing_value(sqlite_db, memory_db):
    sqlite_db[b"1"] = b"1"
    sqlite_db[b"1"] = b"2"
    assert sqlite_db[b"1"] == b"2"

    memory_db[b"1"] = b"1"
    memory_db[b"1"] = b"2"
    assert memory_db[b"1"] == b"2"


def test_exists(sqlite_db, memory_db):
    sqlite_db.set(b"1", b"1")
    assert sqlite_db.exists(b"1")
    memory_db.set(b"1", b"1")
    assert memory_db.exists(b"1")


def test_delete(sqlite_db, memory_db):
    sqlite_db.set(b"1", b"1")
    sqlite_db.delete(b"1")
    assert not sqlite_db.exists(b"1")

    memory_db.set(b"1", b"1")
    memory_db.delete(b"1")
    assert not memory_db.exists(b"1")
