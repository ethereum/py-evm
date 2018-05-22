from abc import abstractmethod
import asyncio
from pathlib import Path
from multiprocessing.managers import (
    BaseManager,
)
from threading import Thread
from typing import List, Type

from evm.chains.base import BaseChain
from evm.db.header import BaseHeaderDB
from p2p.service import (
    BaseService,
    EmptyService,
)
from p2p.utils import (
    RunningServices,
)
from trinity.chains import (
    ChainProxy,
)
from trinity.chains.header import (
    AsyncHeaderChainProxy,
)
from trinity.db.chain import ChainDBProxy
from trinity.db.base import DBProxy
from trinity.db.header import AsyncHeaderDBProxy
from trinity.rpc.main import (
    RPCServer,
)
from trinity.rpc.ipc import (
    IPCServer,
)
from trinity.utils.chains import (
    ChainConfig,
)


class Node(BaseService):
    """
    Create usable nodes by adding subclasses that define the following
    unset attributes.
    """
    chain_class: Type[BaseChain] = None

    _peer_service: BaseService = None

    def __init__(self, chain_config: ChainConfig) -> None:
        super().__init__()

        self._db_manager = create_db_manager(chain_config.database_ipc_path)
        self._headerdb = self._db_manager.get_headerdb()  # type: ignore

        self._jsonrpc_ipc_path: Path = chain_config.jsonrpc_ipc_path
        self._auxiliary_services: List[BaseService] = []

    @abstractmethod
    def get_chain(self) -> BaseChain:
        raise NotImplementedError("Node classes must implement this method")

    @abstractmethod
    def get_peer_service(self) -> BaseService:
        """
        This is the main service that will be run, when calling :meth:`run`.
        It's typically responsible for syncing the chain, with peer connections.
        """
        raise NotImplementedError("Node classes must implement this method")

    @property
    def db_manager(self) -> BaseManager:
        return self._db_manager

    @property
    def headerdb(self) -> BaseHeaderDB:
        return self._headerdb

    def add_service(self, service: BaseService) -> None:
        self._auxiliary_services.append(service)

    def make_ipc_server(self) -> IPCServer:
        if self._jsonrpc_ipc_path:
            rpc = RPCServer(self.get_chain())
            return IPCServer(rpc, self._jsonrpc_ipc_path)
        else:
            return EmptyService()

    async def _run(self):
        ipc_server = self.make_ipc_server()

        # The RPC server needs its own thread, because it provides a synchcronous
        # API which might call into p2p async methods. These sync->async calls
        # deadlock if they are run in the same Thread and loop.
        ipc_loop = self._make_new_loop_thread()

        # keep a copy on self, for debugging
        self._ipc_server, self._ipc_loop = ipc_server, ipc_loop

        try:
            asyncio.run_coroutine_threadsafe(ipc_server.run(loop=ipc_loop), loop=ipc_loop)

            async with RunningServices(self._auxiliary_services):
                await self.get_peer_service().run()
        finally:
            await ipc_server.stop()

    async def _cleanup(self):
        await self.get_peer_service().stop()

    def _make_new_loop_thread(self):
        new_loop = asyncio.new_event_loop()

        def start_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()

        thread = Thread(target=start_loop, args=(new_loop, ))
        thread.start()

        return new_loop


def create_db_manager(ipc_path: str) -> BaseManager:
    """
    We're still using 'str' here on param ipc_path because an issue with
    multi-processing not being able to interpret 'Path' objects correctly
    """
    class DBManager(BaseManager):
        pass

    # Typeshed definitions for multiprocessing.managers is incomplete, so ignore them for now:
    # https://github.com/python/typeshed/blob/85a788dbcaa5e9e9a62e55f15d44530cd28ba830/stdlib/3/multiprocessing/managers.pyi#L3
    DBManager.register('get_db', proxytype=DBProxy)  # type: ignore
    DBManager.register('get_chaindb', proxytype=ChainDBProxy)  # type: ignore
    DBManager.register('get_chain', proxytype=ChainProxy)  # type: ignore
    DBManager.register('get_headerdb', proxytype=AsyncHeaderDBProxy)  # type: ignore
    DBManager.register('get_header_chain', proxytype=AsyncHeaderChainProxy)  # type: ignore

    manager = DBManager(address=ipc_path)  # type: ignore
    manager.connect()  # type: ignore
    return manager
