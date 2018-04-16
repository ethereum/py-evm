import logging
from evm.db.backends.base import BaseDB


class BatchDB(BaseDB):
    """
    A wrapper of basic DB objects with uncommitted DB changes stored in local cache,
    which represents as a dictionary of database keys and values.
    This class should be usable as a context manager, the changes either all fail or all succeed.
    Upon exiting the context, it writes all of the key value pairs from the cache into
    the underlying database. If anyerror occurred before committing phase,
    we would not apply commits at all.
    """
    logger = logging.getLogger("evm.db.BatchDB")

    def __init__(self, wrapped_db):
        self.wrapped_db = wrapped_db
        self.cache = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # commit all the changes from local cache to underlying db
        if exc_type is None:
            for key, value in self.cache.items():
                self.wrapped_db.set(key, value)
        else:
            self.logger.error("Unexpected error %s occurred when batch update", repr(exc_val))
        self.cache = {}
        return True

    def exists(self, key):
        return key in self.cache or self.wrapped_db.exists(key)

    # if not key is found, return None
    def get(self, key):
        if key in self.cache:
            return self.cache[key]
        else:
            try:
                current_value = self.wrapped_db.get(key)
            except KeyError:
                current_value = None
            return current_value

    def set(self, key, value):
        self.cache[key] = value

    def delete(self, key):
        self.cache.pop(key, None)

    #
    # Dictionary API
    #
    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        return self.set(key, value)

    def __delitem__(self, key):
        return self.delete(key)

    def __contains__(self, key):
        return self.exists(key)
