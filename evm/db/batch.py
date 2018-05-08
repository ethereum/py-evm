import logging
from typing import Type, Dict  # noqa: F401

from evm.db.diff import (
    DBDiff,
    DBDiffTracker,
    DiffMissingError,
)
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
    _track_diff = None  # type: DBDiffTracker

    def __init__(self, wrapped_db: BaseDB) -> None:
        self.wrapped_db = wrapped_db
        self._track_diff = DBDiffTracker()

    def __enter__(self) -> 'BatchDB':
        return self

    def __exit__(self, exc_type: None, exc_value: None, traceback: None) -> None:
        # commit all the changes from local cache to underlying db
        if exc_type is None:
            self.commit()
        else:
            self.clear()
            self.logger.exception("Unexpected error occurred during batch update")

    def clear(self):
        self._track_diff = DBDiffTracker()

    def commit(self):
        self.diff().apply_to(self.wrapped_db)
        self.clear()

    def _exists(self, key: bytes) -> bool:
        try:
            self[key]
        except KeyError:
            return False
        else:
            return True

    def __getitem__(self, key: bytes) -> bytes:
        try:
            value = self._track_diff[key]
        except DiffMissingError as missing:
            if missing.is_deleted:
                raise KeyError(key)
            else:
                return self.wrapped_db[key]
        else:
            return value

    def __setitem__(self, key: bytes, value: bytes) -> None:
        self._track_diff[key] = value

    def __delitem__(self, key: bytes) -> None:
        if key not in self:
            raise KeyError(key)
        del self._track_diff[key]

    def diff(self) -> DBDiff:
        return self._track_diff.diff()
