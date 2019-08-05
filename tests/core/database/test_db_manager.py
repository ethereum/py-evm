from eth.db.atomic import AtomicDB

import pathlib
import pytest
import tempfile
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
def db():
    return AtomicDB()


def test_db_manager_lifecycle(db, ipc_path):
    manager = DBManager(db)

    assert not manager.is_running
    assert not manager.is_stopped

    with manager.run(ipc_path):
        assert manager.is_running
        assert not manager.is_stopped

    assert not manager.is_running
    assert manager.is_stopped


def test_db_manager_lifecycle_with_connections(db, ipc_path):
    manager = DBManager(db)

    assert not manager.is_running
    assert not manager.is_stopped

    with manager.run(ipc_path):
        assert manager.is_running
        assert not manager.is_stopped

        client_a = DBClient.connect(ipc_path)
        client_b = DBClient.connect(ipc_path)

        assert manager.is_running
        assert not manager.is_stopped

    client_a.close()
    client_b.close()

    assert not manager.is_running
    assert manager.is_stopped
