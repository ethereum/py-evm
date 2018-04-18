import logging
from typing import Type, Dict  # noqa: F401

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

    wrapped_db = None  # type: BaseDB
    cache = None  # type: Dict[bytes, bytes]

    def __init__(self, wrapped_db: BaseDB) -> None:
        self.wrapped_db = wrapped_db
        self.cache = {}  # type: Dict[bytes, bytes]

    def __enter__(self) -> 'BatchDB':
        return self

    def __exit__(self, exc_type: None, exc_value: None, traceback: None) -> None:
        # commit all the changes from local cache to underlying db
        if exc_type is None:
            self.commit()
        else:
            self.clear()
            self.logger.exception("Unexpected error occurred when batch update")

    def clear(self):
        self.cache = {}

    def commit(self):
        for key, value in self.cache.items():
            if value is None:
                try:
                    del self.wrapped_db[key]
                except KeyError:
                    pass
            else:
                self.wrapped_db[key] = value

        self.clear()

    def exists(self, key: bytes) -> bool:
        try:
            return self.cache[key] is not None
        except KeyError:
            return key in self.wrapped_db

    # if not key is found, return None
    def get(self, key: bytes) -> bytes:
        try:
            value = self.cache[key]
        except KeyError:
            return self.wrapped_db[key]
        else:
            if value is None:
                raise KeyError(key)
            return value

    def set(self, key: bytes, value: bytes) -> None:
        self.cache[key] = value

    def delete(self, key: bytes) -> None:
        if key not in self:
            raise KeyError(key)
        self.cache[key] = None
