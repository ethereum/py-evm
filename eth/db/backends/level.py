from contextlib import contextmanager
import logging
from pathlib import Path
from typing import Generator

from .base import (
    BaseAtomicDB,
)


class LevelDB(BaseAtomicDB):
    logger = logging.getLogger("eth.db.backends.LevelDB")

    # Creates db as a class variable to avoid level db lock error
    def __init__(self, db_path: Path = None) -> None:
        if not db_path:
            raise TypeError("Please specifiy a valid path for your database.")
        try:
            import plyvel
        except ImportError:
            raise ImportError("LevelDB requires the plyvel \
                               library which is not available for import.")
        self.db_path = db_path
        self.db = plyvel.DB(str(db_path), create_if_missing=True, error_if_exists=False)

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
        self.db.delete(key)

    @contextmanager
    def atomic_batch(self) -> Generator[None, None, None]:
        with self.db.write_batch(transaction=True):
            try:
                yield
            except Exception:
                self.logger.exception("Unexpected error occurred during atomic database write")
                raise
