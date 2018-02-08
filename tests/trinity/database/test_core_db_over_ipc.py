import multiprocessing
import os
import tempfile

import pytest

from trinity.db.core import (
    PipeDB,
)
from trinity.utils.db import (
    MemoryDB,
)
from trinity.utils.ipc import (
    wait_for_ipc,
    kill_processes_gracefully,
    serve_object_over_ipc,
)


@pytest.fixture
def core_db_ipc_path():
    base_db = MemoryDB()
    base_db[b'key-a'] = b'value-a'
    base_db[b'key-b'] = b'value-b'

    with tempfile.TemporaryDirectory() as temp_dir:
        ipc_path = os.path.join(temp_dir, 'db.ipc')

        db_server_process = multiprocessing.Process(
            target=serve_object_over_ipc,
            args=(base_db, ipc_path),
        )
        db_server_process.start()

        wait_for_ipc(ipc_path)

        try:
            yield ipc_path
        finally:
            kill_processes_gracefully(db_server_process)


def test_core_db_over_ipc_server(core_db_ipc_path):
    db = PipeDB(core_db_ipc_path)

    assert db[b'key-a'] == b'value-a'
    assert db[b'key-b'] == b'value-b'

    assert b'key-c' not in db
    db[b'key-c'] = b'value-c'
    assert b'key-c' in db
    assert db[b'key-c'] == b'value-c'

    assert b'key-b' in db
    del db[b'key-b']
    assert b'key-b' not in db
