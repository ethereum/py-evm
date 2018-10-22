from multiprocessing.managers import (
    BaseManager,
)
import pathlib

from eth.db.backends.base import BaseAtomicDB

from trinity.config import TrinityConfig
from trinity.db.base import DBProxy
from trinity.db.chain import AsyncChainDB, ChainDBProxy
from trinity.db.header import (
    AsyncHeaderDB,
    AsyncHeaderDBProxy,
)
from trinity.initialization import (
    is_database_initialized,
    initialize_database,
)
from trinity.utils.mp import TracebackRecorder


def get_chaindb_manager(trinity_config: TrinityConfig, base_db: BaseAtomicDB) -> BaseManager:
    chain_config = trinity_config.get_chain_config()
    chaindb = AsyncChainDB(base_db)

    if not is_database_initialized(chaindb):
        initialize_database(chain_config, chaindb, base_db)

    headerdb = AsyncHeaderDB(base_db)

    class DBManager(BaseManager):
        pass

    DBManager.register(
        'get_db', callable=lambda: TracebackRecorder(base_db), proxytype=DBProxy)

    DBManager.register(
        'get_chaindb',
        callable=lambda: TracebackRecorder(chaindb),
        proxytype=ChainDBProxy,
    )

    DBManager.register(
        'get_headerdb',
        callable=lambda: TracebackRecorder(headerdb),
        proxytype=AsyncHeaderDBProxy,
    )

    manager = DBManager(address=str(trinity_config.database_ipc_path))  # type: ignore
    return manager


def create_db_manager(ipc_path: pathlib.Path) -> BaseManager:
    """
    We're still using 'str' here on param ipc_path because an issue with
    multi-processing not being able to interpret 'Path' objects correctly
    """
    class DBManager(BaseManager):
        pass

    DBManager.register('get_db', proxytype=DBProxy)
    DBManager.register('get_chaindb', proxytype=ChainDBProxy)
    DBManager.register('get_headerdb', proxytype=AsyncHeaderDBProxy)

    manager = DBManager(address=str(ipc_path))  # type: ignore
    return manager
