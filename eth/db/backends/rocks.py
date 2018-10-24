from contextlib import contextmanager
import logging
from pathlib import Path
from typing import (
    Iterable,
    TYPE_CHECKING,
)

from eth_utils import ValidationError

from eth.db.diff import (
    DBDiffTracker,
    DiffMissingError,
)
from .base import (
    BaseAtomicDB,
    BaseDB,
)

if TYPE_CHECKING:
    import rocksdb  # noqa: F401


class RocksDB(BaseAtomicDB):
    logger = logging.getLogger("eth.db.backends.RocksDB")

    def __init__(self,
                 db_path: Path = None,
                 opts: 'rocksdb.Options' = None,
                 read_only: bool=False) -> None:
        if not db_path:
            raise TypeError("The RocksDB backend requires a database path")
        try:
            import rocksdb  # noqa: F811
        except ImportError:
            raise ImportError(
                "RocksDB requires the python-rocksdb library which is not "
                "available for import."
            )

        if opts is None:
            opts = rocksdb.Options(create_if_missing=True)
        self.db_path = db_path
        self.db = rocksdb.DB(str(db_path), opts, read_only=read_only)

    def __getitem__(self, key: bytes) -> bytes:
        v = self.db.get(key)
        if v is None:
            raise KeyError(key)
        return v

    def __setitem__(self, key: bytes, value: bytes) -> None:
        self.db.put(key, value)

    def _exists(self, key: bytes) -> bool:
        return self.db.get(key) is not None

    def __delitem__(self, key: bytes) -> None:
        exists, _ = self.db.key_may_exist(key)
        if not exists:
            raise KeyError(key)
        self.db.delete(key)

    @contextmanager
    def atomic_batch(self) -> Iterable['RocksDBWriteBatch']:
        import rocksdb  # noqa: F811
        batch = rocksdb.WriteBatch()

        readable_batch = RocksDBWriteBatch(self, batch)

        try:
            yield readable_batch
        finally:
            readable_batch.decommission()

        self.db.write(batch)


class RocksDBWriteBatch(BaseDB):
    """
    A native rocksdb write batch does not permit reads on the in-progress data.
    This class fills that gap, by tracking the in-progress diff, and adding
    a read interface.
    """
    logger = logging.getLogger("eth.db.backends.RocksDBWriteBatch")

    def __init__(self, original_read_db: BaseDB, write_batch: 'rocksdb.WriteBatch') -> None:
        self._original_read_db = original_read_db
        self._write_batch = write_batch
        # keep track of the temporary changes made
        self._track_diff = DBDiffTracker()

    def __getitem__(self, key: bytes) -> bytes:
        if self._track_diff is None:
            raise ValidationError("Cannot get data from a write batch, out of context")

        try:
            changed_value = self._track_diff[key]
        except DiffMissingError as missing:
            if missing.is_deleted:
                raise KeyError(key)
            else:
                return self._original_read_db[key]
        else:
            return changed_value

    def __setitem__(self, key: bytes, value: bytes) -> None:
        if self._track_diff is None:
            raise ValidationError("Cannot set data from a write batch, out of context")

        self._write_batch.put(key, value)
        self._track_diff[key] = value

    def _exists(self, key: bytes) -> bool:
        if self._track_diff is None:
            raise ValidationError("Cannot test data existance from a write batch, out of context")

        try:
            self._track_diff[key]
        except DiffMissingError as missing:
            if missing.is_deleted:
                return False
            else:
                return key in self._original_read_db
        else:
            return True

    def __delitem__(self, key: bytes) -> None:
        if self._track_diff is None:
            raise ValidationError("Cannot delete data from a write batch, out of context")

        self._write_batch.delete(key)
        del self._track_diff[key]

    def decommission(self) -> None:
        """
        Prevent any further actions to be taken on this write batch, called after leaving context
        """
        self._track_diff = None
