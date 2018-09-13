from multiprocessing.managers import (
    BaseManager,
)
import pathlib
from typing import Type

from eth import MainnetChain, RopstenChain
from eth.chains.base import BaseChain
from eth.db.backends.base import BaseAtomicDB

from trinity.chains.header import (
    AsyncHeaderChain,
    AsyncHeaderChainProxy,
)
from trinity.chains.proxy import ChainProxy
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
from trinity.constants import (
    MAINNET_NETWORK_ID,
    ROPSTEN_NETWORK_ID,
)
from trinity.utils.mp import TracebackRecorder


def get_chaindb_manager(trinity_config: TrinityConfig, base_db: BaseAtomicDB) -> BaseManager:
    chaindb = AsyncChainDB(base_db)
    if not is_database_initialized(chaindb):
        initialize_database(trinity_config, chaindb)

    chain_class: Type[BaseChain]
    chain: BaseChain

    if trinity_config.network_id == MAINNET_NETWORK_ID:
        chain_class = MainnetChain
        chain = chain_class(base_db)
    elif trinity_config.network_id == ROPSTEN_NETWORK_ID:
        chain_class = RopstenChain
        chain = chain_class(base_db)
    else:
        raise NotImplementedError("Only the ropsten and mainnet chains are supported")

    headerdb = AsyncHeaderDB(base_db)
    header_chain = AsyncHeaderChain(base_db)

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
        'get_chain', callable=lambda: TracebackRecorder(chain), proxytype=ChainProxy)

    DBManager.register(
        'get_headerdb',
        callable=lambda: TracebackRecorder(headerdb),
        proxytype=AsyncHeaderDBProxy,
    )
    DBManager.register(
        'get_header_chain',
        callable=lambda: TracebackRecorder(header_chain),
        proxytype=AsyncHeaderChainProxy,
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
    DBManager.register('get_chain', proxytype=ChainProxy)
    DBManager.register('get_headerdb', proxytype=AsyncHeaderDBProxy)
    DBManager.register('get_header_chain', proxytype=AsyncHeaderChainProxy)

    manager = DBManager(address=str(ipc_path))  # type: ignore
    return manager
