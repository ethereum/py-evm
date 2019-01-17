from multiprocessing.managers import (
    BaseManager,
)
import pathlib

from eth2.beacon.db.chain import BeaconChainDB
from eth.db.backends.base import BaseAtomicDB

from trinity.config import TrinityConfig
from trinity.db.base import AsyncDBProxy
from trinity.db.beacon.chain import AsyncBeaconChainDBProxy

from trinity._utils.mp import TracebackRecorder


def create_db_server_manager(trinity_config: TrinityConfig,
                             base_db: BaseAtomicDB) -> BaseManager:

    chaindb = BeaconChainDB(base_db)

    # TODO: handle initialization

    class DBManager(BaseManager):
        pass

    DBManager.register(
        'get_db', callable=lambda: TracebackRecorder(base_db), proxytype=AsyncDBProxy)

    DBManager.register(
        'get_chaindb',
        callable=lambda: TracebackRecorder(chaindb),
        proxytype=AsyncBeaconChainDBProxy,
    )

    manager = DBManager(address=str(trinity_config.database_ipc_path))  # type: ignore
    return manager


def create_db_consumer_manager(ipc_path: pathlib.Path, connect: bool=True) -> BaseManager:
    """
    We're still using 'str' here on param ipc_path because an issue with
    multi-processing not being able to interpret 'Path' objects correctly
    """
    class DBManager(BaseManager):
        pass

    DBManager.register('get_db', proxytype=AsyncDBProxy)
    DBManager.register('get_chaindb', proxytype=AsyncBeaconChainDBProxy)

    manager = DBManager(address=str(ipc_path))  # type: ignore
    if connect:
        manager.connect()
    return manager
