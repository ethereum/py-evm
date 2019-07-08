import multiprocessing
from multiprocessing.managers import (
    BaseManager,
)
import pathlib

from eth.db.chain import ChainDB
from eth.db.backends.base import BaseAtomicDB
from eth.db.header import HeaderDB

from trinity.config import (
    Eth1AppConfig,
    TrinityConfig,
)
from trinity.db.base import AsyncDBProxy
from trinity.db.eth1.chain import AsyncChainDBProxy
from trinity.db.eth1.header import (
    AsyncHeaderDBProxy
)
from trinity.initialization import (
    is_database_initialized,
    initialize_database,
)
from trinity._utils.mp import TracebackRecorder

AUTH_KEY = b"not secure, but only connect over IPC"


def create_db_server_manager(trinity_config: TrinityConfig,
                             base_db: BaseAtomicDB) -> BaseManager:

    eth1_app_config = trinity_config.get_app_config(Eth1AppConfig)
    chain_config = eth1_app_config.get_chain_config()
    chaindb = ChainDB(base_db)

    if not is_database_initialized(chaindb):
        initialize_database(chain_config, chaindb, base_db)

    headerdb = HeaderDB(base_db)

    # This enables connection when clients launch from another process on the shell
    multiprocessing.current_process().authkey = AUTH_KEY

    class DBManager(BaseManager):
        pass

    DBManager.register(
        'get_db', callable=lambda: TracebackRecorder(base_db), proxytype=AsyncDBProxy)

    DBManager.register(
        'get_chaindb',
        callable=lambda: TracebackRecorder(chaindb),
        proxytype=AsyncChainDBProxy,
    )

    DBManager.register(
        'get_headerdb',
        callable=lambda: TracebackRecorder(headerdb),
        proxytype=AsyncHeaderDBProxy,
    )

    manager = DBManager(address=str(trinity_config.database_ipc_path))  # type: ignore
    return manager


def create_db_consumer_manager(ipc_path: pathlib.Path, connect: bool=True) -> BaseManager:
    """
    We're still using 'str' here on param ipc_path because an issue with
    multi-processing not being able to interpret 'Path' objects correctly
    """
    # This enables connection when launched from another process on the shell
    multiprocessing.current_process().authkey = AUTH_KEY

    class DBManager(BaseManager):
        pass

    DBManager.register('get_db', proxytype=AsyncDBProxy)
    DBManager.register('get_chaindb', proxytype=AsyncChainDBProxy)
    DBManager.register('get_headerdb', proxytype=AsyncHeaderDBProxy)

    manager = DBManager(address=str(ipc_path))  # type: ignore
    if connect:
        manager.connect()
    return manager
