import multiprocessing
from multiprocessing.managers import (
    BaseManager,
)
import tempfile

import pytest

from evm.chains.ropsten import ROPSTEN_GENESIS_HEADER, ROPSTEN_NETWORK_ID

from trinity.chains import (
    serve_chaindb,
)
from trinity.db.chain import (
    AsyncChainDBProxy,
)
from trinity.db.header import (
    AsyncHeaderDB,
    AsyncHeaderDBProxy,
)
from trinity.db.base import DBProxy
from trinity.utils.chains import (
    ChainConfig,
)
from trinity.utils.db import (
    MemoryDB,
)
from trinity.utils.ipc import (
    wait_for_ipc,
    kill_process_gracefully,
)


@pytest.fixture
def database_server_ipc_path():
    base_db = MemoryDB()
    base_db[b'key-a'] = b'value-a'

    # persist the genesis header
    headerdb = AsyncHeaderDB(base_db)
    headerdb.persist_header(ROPSTEN_GENESIS_HEADER)

    with tempfile.TemporaryDirectory() as temp_dir:
        chain_config = ChainConfig(network_id=ROPSTEN_NETWORK_ID, data_dir=temp_dir)

        chaindb_server_process = multiprocessing.Process(
            target=serve_chaindb,
            args=(chain_config, base_db),
        )
        chaindb_server_process.start()

        wait_for_ipc(chain_config.database_ipc_path)

        try:
            yield chain_config.database_ipc_path
        finally:
            kill_process_gracefully(chaindb_server_process)


@pytest.fixture
def manager(database_server_ipc_path):
    class DBManager(BaseManager):
        pass

    DBManager.register('get_db', proxytype=DBProxy)

    DBManager.register('get_chaindb', proxytype=AsyncChainDBProxy)
    DBManager.register('get_headerdb', proxytype=AsyncHeaderDBProxy)

    _manager = DBManager(address=database_server_ipc_path)
    _manager.connect()
    return _manager


def test_headerdb_over_ipc_manager(manager):
    headerdb = manager.get_headerdb()

    header = headerdb.get_canonical_head()

    assert header == ROPSTEN_GENESIS_HEADER


def test_chaindb_over_ipc_manager(manager):
    chaindb = manager.get_chaindb()

    # TODO: what should we test here
    assert False


def test_db_over_ipc_manager(manager):
    db = manager.get_db()

    assert b'key-a' in db
    assert db[b'key-a'] == b'value-a'

    with pytest.raises(KeyError):
        db[b'not-present']
