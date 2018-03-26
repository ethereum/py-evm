from evm.db.backends.base import BaseDB


class ImmutableDB(BaseDB):
    _wrapped_db = None

    def __init__(self, wrapped_db: BaseDB) -> None:
        self._wrapped_db = wrapped_db

    def get(self, key: bytes) -> bytes:
        return self._wrapped_db.get(key)

    def set(self, key: bytes, value: bytes) -> None:
        raise TypeError("Current database is immutable and does not support setting of keys.")

    def exists(self, key: bytes) -> bool:
        return self._wrapped_db.exists(key)

    def delete(self, key: bytes) -> None:
        raise TypeError("Current database is immutable and does not support setting of keys.")
