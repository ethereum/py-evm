from hypothesis import (
    given,
    strategies as st,
)
import pytest

from eth.db.accesslog import (
    KeyAccessLoggerAtomicDB,
    KeyAccessLoggerDB,
)
from eth.db.backends.memory import (
    MemoryDB,
)


@given(st.lists(st.binary()))
@pytest.mark.parametrize(
    "DB",
    (
        lambda: KeyAccessLoggerAtomicDB(MemoryDB()),
        lambda: KeyAccessLoggerAtomicDB(MemoryDB(), log_missing_keys=False),
        lambda: KeyAccessLoggerAtomicDB(MemoryDB(), log_missing_keys=True),
        lambda: KeyAccessLoggerDB(MemoryDB()),
        lambda: KeyAccessLoggerDB(MemoryDB(), log_missing_keys=False),
        lambda: KeyAccessLoggerDB(MemoryDB(), log_missing_keys=True),
    ),
)
def test_log_accesses(DB, keys):
    db = DB()
    assert len(db.keys_read) == 0
    for key in keys:
        db[key] = b"placeholder"  # value doesn't matter
        assert db[key] == b"placeholder"

    for key in keys:
        assert key in db.keys_read


@pytest.mark.parametrize(
    "DB",
    (
        lambda: KeyAccessLoggerAtomicDB(MemoryDB()),
        lambda: KeyAccessLoggerAtomicDB(MemoryDB(), log_missing_keys=True),
        lambda: KeyAccessLoggerDB(MemoryDB()),
        lambda: KeyAccessLoggerDB(MemoryDB(), log_missing_keys=True),
    ),
)
def test_logs_missing_keys(DB):
    db_logs_missing = DB()
    assert len(db_logs_missing.keys_read) == 0
    assert b"exist-test" not in db_logs_missing

    assert b"exist-test" in db_logs_missing.keys_read

    with pytest.raises(KeyError, match="get-test"):
        db_logs_missing[b"get-test"]

    assert b"get-test" in db_logs_missing.keys_read
    assert len(db_logs_missing.keys_read) == 2


@pytest.mark.parametrize(
    "DB",
    (
        lambda: KeyAccessLoggerAtomicDB(MemoryDB(), log_missing_keys=False),
        lambda: KeyAccessLoggerDB(MemoryDB(), log_missing_keys=False),
    ),
)
def test_dont_log_missing_keys(DB):
    db_doesnt_log_missing = DB()
    assert len(db_doesnt_log_missing.keys_read) == 0
    assert b"exist-test" not in db_doesnt_log_missing

    assert b"exist-test" not in db_doesnt_log_missing.keys_read

    with pytest.raises(KeyError, match="get-test"):
        db_doesnt_log_missing[b"get-test"]

    assert b"get-test" not in db_doesnt_log_missing.keys_read
    assert len(db_doesnt_log_missing.keys_read) == 0
