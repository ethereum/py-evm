from eth.db.atomic import AtomicDB

import pathlib
import pytest
import tempfile

from eth.tools.db.atomic import AtomicDatabaseBatchAPITestSuite
from eth.tools.db.base import DatabaseAPITestSuite

from trinity.db.manager import (
    DBManager,
    DBClient,
)


@pytest.fixture
def ipc_path():
    with tempfile.TemporaryDirectory() as dir:
        ipc_path = pathlib.Path(dir) / "db_manager.ipc"
        yield ipc_path


@pytest.fixture
def base_db():
    return AtomicDB()


@pytest.fixture
def db_manager(base_db, ipc_path):
    with DBManager(base_db).run(ipc_path) as manager:
        yield manager


@pytest.fixture
def db_client(ipc_path, db_manager):
    client = DBClient.connect(ipc_path)
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def db(db_client):
    return db_client


@pytest.fixture
def atomic_db(db):
    return db


class TestDBClientDatabaseAPI(DatabaseAPITestSuite):
    pass


class TestDBClientAtomicBatchAPI(AtomicDatabaseBatchAPITestSuite):
    pass
