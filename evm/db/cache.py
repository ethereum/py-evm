from lru import LRU

from evm.db.backends.base import BaseDB


class CacheDB(BaseDB):
    """
    Set and get decoded RLP objects, where the underlying db stores
    encoded objects.
    """
    def __init__(self, db, cache_size=2048):
        self._db = db
        self._cache_size = cache_size
        self.reset_cache()

    def reset_cache(self):
        self._cached_values = LRU(self._cache_size)

    def __getitem__(self, key):
        if key not in self._cached_values:
            self._cached_values[key] = self._db[key]
        return self._cached_values[key]

    def __setitem__(self, key, value):
        self._cached_values[key] = value
        self._db[key] = value

    def __delitem__(self, key):
        if key in self._cached_values:
            del self._cached_values[key]
        del self._db[key]
