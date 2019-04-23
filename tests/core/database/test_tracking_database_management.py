import asyncio
from pathlib import Path
import uuid

import pytest

from p2p.exceptions import BadDatabaseError

from trinity.db.orm import (
    SchemaVersion,
    Base,
    _setup_schema,
    _check_is_empty,
    _check_tables_exist,
    _check_schema_version,
    _get_schema_version,
    _get_session,
    get_tracking_database,
    SCHEMA_VERSION,
)


@pytest.fixture
def session():
    path = Path(':memory:')
    return _get_session(path)


@pytest.fixture
def db_path(tmpdir):
    path = Path(str(tmpdir.join('nodedb.sqlite')))
    return path


#
# Schema initialization tests
#
def test_get_schema_version(session):
    _setup_schema(session)
    version = _get_schema_version(session)
    assert version == SCHEMA_VERSION


def test_setup_schema(session):
    assert _check_schema_version(session) is False
    _setup_schema(session)
    assert _check_schema_version(session) is True


def test_check_schema_version_false_when_no_tables(session):
    assert _check_is_empty(session)
    assert _check_schema_version(session) is False


def test_check_schema_version_false_when_no_entry(session):
    _setup_schema(session)
    assert _check_schema_version(session) is True

    # delete the entry
    schema_version = session.query(SchemaVersion).one()
    session.delete(schema_version)
    session.commit()

    assert _check_schema_version(session) is False


def test_check_schema_version_false_when_wrong_version(session):
    _setup_schema(session)

    assert _check_schema_version(session) is True

    # change version to unknown value
    schema_version = session.query(SchemaVersion).one()
    schema_version.version = 'unknown'

    session.add(schema_version)
    session.commit()

    assert _check_schema_version(session) is False


def test_check_tables_exist(session):
    assert _check_tables_exist(session) is False
    _setup_schema(session)
    assert _check_tables_exist(session) is True


def test_check_tables_exist_missing_table(session):
    assert _check_tables_exist(session) is False
    _setup_schema(session)
    assert _check_tables_exist(session) is True
    engine = session.get_bind()
    assert engine.has_table('schema_version') is True
    table = Base.metadata.tables['schema_version']
    table.drop(engine)
    assert engine.has_table('schema_version') is False
    assert _check_tables_exist(session) is False


def test_check_schema_version_false_when_multiple_entries(session):
    _setup_schema(session)

    assert _check_schema_version(session) is True

    session.add(SchemaVersion(version='unknown'))
    session.commit()

    assert _check_schema_version(session) is False


def test_get_tracking_db_from_empty():
    session = get_tracking_database(Path(':memory:'))
    assert _check_schema_version(session) is True


def test_get_tracking_db_from_valid_existing(db_path):
    session_a = get_tracking_database(db_path)
    assert _check_schema_version(session_a) is True
    del session_a

    # ensure the session was persisted to disk
    session_b = _get_session(db_path)
    assert _check_schema_version(session_b) is True
    del session_b

    session_c = get_tracking_database(db_path)
    assert _check_schema_version(session_c) is True


def test_get_tracking_db_errors_bad_schema_version(db_path):
    session_a = get_tracking_database(db_path)
    assert _check_schema_version(session_a) is True

    # change version to unknown value
    schema_version = session_a.query(SchemaVersion).one()
    schema_version.version = 'unknown'

    session_a.add(schema_version)
    session_a.commit()
    del session_a

    # ensure the session was persisted to disk
    session_b = _get_session(db_path)
    assert _check_schema_version(session_b) is False
    del session_b

    with pytest.raises(BadDatabaseError):
        get_tracking_database(db_path)


@pytest.mark.asyncio
async def test_db_can_have_different_concurrent_sessions(db_path):
    _setup_schema(_get_session(db_path))

    async def read_and_write():
        for _ in range(10):
            session = _get_session(db_path)
            # change version to unknown value
            schema_version = session.query(SchemaVersion).one()
            await asyncio.sleep(0.01)
            schema_version.version = str(uuid.uuid4)
            session.add(schema_version)
            session.commit()
            await asyncio.sleep(0.01)

    await asyncio.gather(
        read_and_write(),
        read_and_write(),
        read_and_write(),
        read_and_write(),
    )
    schema_version = _get_session(db_path).query(SchemaVersion).one()
    print(schema_version.version)
