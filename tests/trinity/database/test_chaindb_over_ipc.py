import multiprocessing
import os
import tempfile

import pytest

from evm.chains.ropsten import ROPSTEN_GENESIS_HEADER
from evm.db.chain import (
    ChainDB,
)

from trinity.db.chaindb import (
    PipeChainDB,
)
from trinity.utils.db import (
    MemoryDB,
)
from trinity.utils.ipc import (
    wait_for_ipc,
    kill_processes_gracefully,
    serve_object_over_ipc,
)


def serve_test_chaindb_over_ipc(ipc_path):
    core_db = MemoryDB()
    chaindb = ChainDB(core_db)
    # TODO: use a custom chain class only for testing.
    chaindb.persist_header_to_db(ROPSTEN_GENESIS_HEADER)
    serve_object_over_ipc(chaindb, ipc_path)


@pytest.fixture
def chaindb_server_ipc_path():
    with tempfile.TemporaryDirectory() as temp_dir:
        ipc_path = os.path.join(temp_dir, 'chaindb.ipc')

        chaindb_server_process = multiprocessing.Process(
            target=serve_test_chaindb_over_ipc,
            args=(ipc_path,),
        )
        chaindb_server_process.start()

        wait_for_ipc(ipc_path)

        try:
            yield ipc_path
        finally:
            kill_processes_gracefully(chaindb_server_process)


def test_database_server(chaindb_server_ipc_path):
    chaindb = PipeChainDB(chaindb_server_ipc_path)

    header = chaindb.get_canonical_head()

    assert header == ROPSTEN_GENESIS_HEADER
