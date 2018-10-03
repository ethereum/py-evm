import logging
import multiprocessing
from multiprocessing.managers import (
    BaseManager,
)
import tempfile

import pytest

from eth.chains.ropsten import ROPSTEN_GENESIS_HEADER
from eth.db.atomic import (
    AtomicDB,
)
from eth.db.chain import (
    ChainDB,
)

from trinity.db.manager import (
    get_chaindb_manager,
)
from trinity.config import (
    TrinityConfig,
)
from trinity.constants import ROPSTEN_NETWORK_ID
from trinity.db.chain import ChainDBProxy
from trinity.db.base import DBProxy
from trinity.utils.ipc import (
    wait_for_ipc,
    kill_process_gracefully,
)


def serve_chaindb(manager):
    server = manager.get_server()
    server.serve_forever()


@pytest.fixture
def database_server_ipc_path():
    core_db = AtomicDB()
    core_db[b'key-a'] = b'value-a'

    chaindb = ChainDB(core_db)
    # TODO: use a custom chain class only for testing.
    chaindb.persist_header(ROPSTEN_GENESIS_HEADER)

    with tempfile.TemporaryDirectory() as temp_dir:
        trinity_config = TrinityConfig(
            network_id=ROPSTEN_NETWORK_ID,
            data_dir=temp_dir,
        )

        manager = get_chaindb_manager(trinity_config, core_db)
        chaindb_server_process = multiprocessing.Process(
            target=serve_chaindb,
            args=(manager,),
        )
        chaindb_server_process.start()

        wait_for_ipc(trinity_config.database_ipc_path)

        try:
            yield trinity_config.database_ipc_path
        finally:
            kill_process_gracefully(chaindb_server_process, logging.getLogger())


@pytest.fixture
def manager(database_server_ipc_path):
    class DBManager(BaseManager):
        pass

    DBManager.register('get_db', proxytype=DBProxy)
    DBManager.register('get_chaindb', proxytype=ChainDBProxy)

    _manager = DBManager(address=str(database_server_ipc_path))
    _manager.connect()
    return _manager


def test_chaindb_over_ipc_manager(manager):
    chaindb = manager.get_chaindb()

    header = chaindb.get_canonical_head()

    assert header == ROPSTEN_GENESIS_HEADER


def test_db_over_ipc_manager(manager):
    db = manager.get_db()

    assert b'key-a' in db
    assert db[b'key-a'] == b'value-a'

    with pytest.raises(KeyError):
        db[b'not-present']
