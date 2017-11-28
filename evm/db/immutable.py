from evm.db.backends.base import BaseDB


class ImmutableDB(BaseDB):
    _wrapped_db = None

    def __init__(self, wrapped_db):
        self._wrapped_db = wrapped_db

    def get(self, key):
        return self._wrapped_db.get(key)

    def set(self, key, value):
        raise TypeError("Current database is immutable and does not support setting of keys.")

    def exists(self, key):
        return self._wrapped_db.exists(key)

    def delete(self, key):
        raise TypeError("Current database is immutable and does not support setting of keys.")
