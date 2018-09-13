from contextlib import contextmanager
import logging
import threading
from typing import Generator

from eth_utils import (
    ValidationError,
)

from eth.db.diff import (
    DBDiff,
    DBDiffTracker,
    DiffMissingError,
)
from eth.db.backends.base import BaseDB, BaseAtomicDB
from eth.db.backends.memory import MemoryDB


class AtomicDB(BaseAtomicDB):
    """
    This is nearly the same as BatchDB, but it immediately writes out changes if they are
    not in a batch_write() context.
    """
    logger = logging.getLogger("eth.db.AtomicDB")

    wrapped_db = None  # type: BaseDB
    _track_diff = None  # type: DBDiffTracker

    def __init__(self, wrapped_db: BaseDB = None) -> None:
        if wrapped_db is None:
            self.wrapped_db = MemoryDB()
        else:
            self.wrapped_db = wrapped_db
        self._track_diff = DBDiffTracker()
        self._batch_lock = threading.Lock()

    @contextmanager
    def atomic_batch(self) -> Generator[None, None, None]:
        if self._batch_lock.locked():
            raise ValidationError("AtomicDB does not support recursive batching of writes")

        try:
            with self._batch_lock:
                yield
        except Exception:
            self.logger.exception(
                "Unexpected error in atomic db write, dropped partial writes: %r",
                self._diff(),
            )
            self._clear()
            raise
        else:
            self._commit()

    def __getitem__(self, key: bytes) -> bytes:
        if not self._batch_lock.locked():
            return self.wrapped_db[key]

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
        if self._batch_lock.locked():
            self._track_diff[key] = value
        else:
            self.wrapped_db[key] = value

    def __delitem__(self, key: bytes) -> None:
        if key not in self:
            raise KeyError(key)
        if self._batch_lock.locked():
            del self._track_diff[key]
        else:
            del self.wrapped_db[key]

    def _diff(self) -> DBDiff:
        return self._track_diff.diff()

    def _clear(self):
        self._track_diff = DBDiffTracker()

    def _commit(self) -> None:
        self._diff().apply_to(self.wrapped_db, apply_deletes=True)
        self._clear()

    def _exists(self, key: bytes) -> bool:
        try:
            self[key]
        except KeyError:
            return False
        else:
            return True
