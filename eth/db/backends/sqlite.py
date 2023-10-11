"""
Builds on the BaseDB class to provider a disk backed key-value store utilizing SQLite3.
"""

import sqlite3
from typing import (
    Iterator,
    Optional,
)

from .base import (
    BaseDB,
)


class SQLiteDB(BaseDB):
    _store: str = "store"
    _connection: Optional[sqlite3.Connection] = None
    _cursor: Optional[sqlite3.Cursor] = None

    def __init__(self, db_path: str, journal_mode: str = "WAL") -> None:
        self.db_path = db_path
        self.journal_mode = journal_mode
        self.connect()
        self._initialize()

    def connect(self) -> None:
        self._connection = sqlite3.connect(self.db_path)
        self._connection.execute(f"PRAGMA journal_mode = {self.journal_mode}")
        self._cursor = self._connection.cursor()

    def _initialize(self) -> None:
        self._cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {self._store} ("
            "key BLOB PRIMARY KEY,"
            "value BLOB"
            ")"
        )
        self._connection.commit()

    def __getitem__(self, key: bytes) -> bytes:
        try:
            return self._cursor.execute(
                f"SELECT value FROM {self._store} WHERE key = ?", (key,)
            ).fetchone()[0]
        except TypeError:
            raise KeyError(key)

    def __setitem__(self, key: bytes, value: bytes) -> None:
        self._cursor.execute(
            f"INSERT OR REPLACE INTO {self._store} VALUES (?, ?)", (key, value)
        )

    def __delitem__(self, key: bytes) -> None:
        self._cursor.execute(f"DELETE FROM {self._store} WHERE key = ?", (key,))

    def __iter__(self) -> Iterator[bytes]:
        return iter(self._cursor.execute(f"SELECT key FROM {self._store}"))

    def __len__(self) -> int:
        return len(list(self._cursor.execute(f"SELECT key FROM {self._store}")))

    def __repr__(self) -> str:
        return f"SQLiteDB({self.db_path!r})"

    def _exists(self, key: bytes) -> bool:
        return bool(
            self._cursor.execute(
                f"SELECT 1 FROM {self._store} WHERE key = ?", (key,)
            ).fetchone()
        )

    def close(self) -> None:
        self._connection.close()
        self._connection = None
