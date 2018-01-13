from .base import (
    BaseDB,
)


class MemoryDB(BaseDB):
    kv_store = None

    def __init__(self, kv_store=None):
        if kv_store is None:
            self.kv_store = {}
        else:
            self.kv_store = kv_store

    def get(self, key):
        return self.kv_store[key]

    def set(self, key, value):
        self.kv_store[key] = value

    def exists(self, key):
        return key in self.kv_store

    def delete(self, key):
        del self.kv_store[key]
