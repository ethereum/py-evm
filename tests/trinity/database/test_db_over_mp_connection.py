import multiprocessing
import os
import tempfile
import time

from trinity.db.pipe import (
    db_server,
    PipeDB,
)
from trinity.utils.mp import (
    wait_for_ipc,
    kill_processes_gracefully,
)
from trinity.utils.db import (
    MemoryDB,
)


def test_database_server():
    base_db = MemoryDB()
    base_db[b'key-a'] = b'value-a'
    base_db[b'key-b'] = b'value-b'

    with tempfile.TemporaryDirectory() as temp_dir:
        ipc_path = os.path.join(temp_dir, 'db.ipc')

        db_server_process = multiprocessing.Process(
            target=db_server,
            args=(base_db, ipc_path),
        )
        db_server_process.start()

        wait_for_ipc(ipc_path)
        time.sleep(0.1)

        db = PipeDB(ipc_path)

        assert db[b'key-a'] == b'value-a'
        assert db[b'key-b'] == b'value-b'

        assert b'key-c' not in db
        db[b'key-c'] = b'value-c'
        assert b'key-c' in db
        assert db[b'key-c'] == b'value-c'

        assert b'key-b' in db
        del db[b'key-b']
        assert b'key-b' not in db

        kill_processes_gracefully(db_server_process)
