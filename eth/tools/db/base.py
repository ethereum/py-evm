import pytest

from eth.abc import (
    DatabaseAPI,
)


class DatabaseAPITestSuite:
    def test_database_api_get(self, db: DatabaseAPI) -> None:
        db[b"key-1"] = b"value-1"
        assert db.get(b"key-1") == b"value-1"

    def test_database_api_item_getter(self, db: DatabaseAPI) -> None:
        db[b"key-1"] = b"value-1"
        assert db[b"key-1"] == b"value-1"

    def test_database_api_get_missing_key(self, db: DatabaseAPI) -> None:
        assert b"key-1" not in db
        assert db.get(b"key-1") is None

    def test_database_api_item_getter_missing_key(self, db: DatabaseAPI) -> None:
        assert b"key-1" not in db
        with pytest.raises(KeyError):
            db[b"key-1"]

    def test_database_api_set(self, db: DatabaseAPI) -> None:
        db[b"key-1"] = b"value-1"
        assert db[b"key-1"] == b"value-1"
        db[b"key-1"] = b"value-2"
        assert db[b"key-1"] == b"value-2"

    def test_database_api_item_setter(self, db: DatabaseAPI) -> None:
        db.set(b"key-1", b"value-1")
        assert db[b"key-1"] == b"value-1"
        db.set(b"key-1", b"value-2")
        assert db[b"key-1"] == b"value-2"

    def test_database_api_exists(self, db: DatabaseAPI) -> None:
        assert db.exists(b"key-1") is False

        db[b"key-1"] = b"value-1"

        assert db.exists(b"key-1") is True

    def test_database_api_contains_checking(self, db: DatabaseAPI) -> None:
        assert b"key-1" not in db

        db[b"key-1"] = b"value-1"

        assert b"key-1" in db

    def test_database_api_delete(self, db: DatabaseAPI) -> None:
        db[b"key-1"] = b"value-1"

        assert b"key-1" in db

        db.delete(b"key-1")

        assert not db.exists(b"key-1")
        assert b"key-1" not in db

    def test_database_api_item_delete(self, db: DatabaseAPI) -> None:
        db[b"key-1"] = b"value-1"

        assert b"key-1" in db

        del db[b"key-1"]

        assert b"key-1" not in db

    def test_database_api_delete_missing_key(self, db: DatabaseAPI) -> None:
        assert b"key-1" not in db
        db.delete(b"key-1")

    def test_database_api_item_delete_missing_key(self, db: DatabaseAPI) -> None:
        assert b"key-1" not in db
        with pytest.raises(KeyError):
            del db[b"key-1"]
