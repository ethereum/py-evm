import pytest

from eth.db.diff import (
    DBDiff,
    DBDiffTracker,
    DiffMissingError,
)


@pytest.fixture
def db():
    return DBDiffTracker()


def test_database_api_get(db):
    db[b"key-1"] = b"value-1"

    assert db.get(b"key-1") == b"value-1"
    assert db[b"key-1"] == b"value-1"


def test_database_api_set(db):
    db[b"key-1"] = b"value-1"
    assert db[b"key-1"] == b"value-1"
    db[b"key-1"] = b"value-2"
    assert db[b"key-1"] == b"value-2"

    db[b"key-1"] = b"value-1"
    assert db[b"key-1"] == b"value-1"
    db[b"key-1"] = b"value-2"
    assert db[b"key-1"] == b"value-2"


def test_database_api_existence_checking(db):
    assert b"key-1" not in db

    db[b"key-1"] = b"value-1"

    assert b"key-1" in db


def test_database_api_delete(db):
    db[b"key-1"] = b"value-1"
    db[b"key-2"] = b"value-2"

    assert b"key-1" in db
    assert b"key-2" in db

    del db[b"key-1"]
    del db[b"key-2"]

    assert b"key-1" not in db
    assert b"key-2" not in db


def test_database_api_missing_key_retrieval(db):
    assert db.get(b"does-not-exist") is None

    try:
        val = db[b"does-not-exist"]
    except DiffMissingError as exc:
        assert not exc.is_deleted
    else:
        raise AssertionError(f"key should be missing, but was retrieved as {val}")


def test_database_api_missing_key_for_deletion(db):
    # no problem to delete a key that is missing
    # (it may be present in the underlying db)
    del db[b"does-not-exist"]

    try:
        val = db[b"does-not-exist"]
    except DiffMissingError as exc:
        assert exc.is_deleted
    else:
        raise AssertionError(f"key should be missing, but was retrieved as {val}")


def test_db_diff_equality(db):
    db[b"key-1"] = b"value-1"
    del db[b"key-2"]

    diff1 = db.diff()
    diff2 = db.diff()
    assert diff1 == diff2

    db[b"key-3"] = b"value-3"
    assert diff1 != db.diff()


def test_database_api_deleted_key_for_deletion(db):
    # create an item, then delete it
    db[b"used-to-exist"] = b"old-value"
    del db[b"used-to-exist"]

    try:
        val = db[b"used-to-exist"]
    except DiffMissingError as exc:
        assert exc.is_deleted
    else:
        raise AssertionError(f"key should be missing, but was retrieved as {val}")


@pytest.mark.parametrize(
    "db, series_of_diffs, expected",
    (
        ({b"0": b"0"}, (), {b"0": b"0"}),
        ({b"0": b"0"}, ({}, {}), {b"0": b"0"}),
        (
            {},
            (
                {b"1": b"1"},
                {b"1": None},
            ),
            {},
        ),
        (
            {},
            (
                {b"1": b"1"},
                {b"1": b"2"},
            ),
            {b"1": b"2"},
        ),
        (
            {b"1": b"0"},
            ({b"1": None},),
            {},
        ),
        (
            {b"1": b"0"},
            ({b"2": b"3"},),
            {b"1": b"0", b"2": b"3"},
        ),
    ),
)
def test_join_diffs(db, series_of_diffs, expected):
    diffs = []
    for changes in series_of_diffs:
        tracker = DBDiffTracker()
        for key, val in changes.items():
            if val is None:
                del tracker[key]
            else:
                tracker[key] = val
        diffs.append(tracker.diff())

    DBDiff.join(diffs).apply_to(db)
    assert db == expected


@pytest.mark.parametrize(
    "series_of_diffs, expected_updates, expected_deletions",
    (
        ((), {}, []),
        (({}, {}), {}, []),
        (
            (
                {b"1": b"1"},
                {b"1": None},
            ),
            {},
            [b"1"],
        ),
        (
            (
                {b"1": b"1"},
                {b"1": b"2"},
            ),
            {b"1": b"2"},
            [],
        ),
        (
            ({b"1": None},),
            {},
            [b"1"],
        ),
        (
            ({b"2": b"3"},),
            {b"2": b"3"},
            [],
        ),
    ),
)
def test_db_diff_inspection(series_of_diffs, expected_updates, expected_deletions):
    diffs = []
    for changes in series_of_diffs:
        tracker = DBDiffTracker()
        for key, val in changes.items():
            if val is None:
                del tracker[key]
            else:
                tracker[key] = val
        diffs.append(tracker.diff())

    actual_diff = DBDiff.join(diffs)
    if expected_updates:
        expected_keys, _ = zip(*expected_updates.items())
    else:
        expected_keys = ()
    assert actual_diff.pending_keys() == expected_keys
    assert actual_diff.pending_items() == tuple(expected_updates.items())
    assert actual_diff.deleted_keys() == tuple(expected_deletions)
