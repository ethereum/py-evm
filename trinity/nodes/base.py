from abc import abstractmethod
from pathlib import Path
from multiprocessing.managers import (
    BaseManager,
)
from typing import (
    Type,
)

from eth.chains.base import BaseChain

from p2p.peer import (
    PeerPool
)
from p2p.service import (
    BaseService,
)
from trinity.chains import (
    ChainProxy,
)
from trinity.chains.header import (
    AsyncHeaderChainProxy,
)
from trinity.db.chain import ChainDBProxy
from trinity.db.base import DBProxy
from trinity.db.header import (
    AsyncHeaderDB,
    AsyncHeaderDBProxy
)
from trinity.rpc.ipc import (
    IPCServiceWrapper,
)
from trinity.config import (
    ChainConfig,
)
from trinity.extensibility import (
    PluginManager,
)
from trinity.extensibility.events import (
    ResourceAvailableEvent
)


class Node(BaseService):
    """
    Create usable nodes by adding subclasses that define the following
    unset attributes.
    """
    chain_config: ChainConfig
    chain_class: Type[BaseChain] = None

    def __init__(self, plugin_manager: PluginManager, chain_config: ChainConfig) -> None:
        super().__init__()
        self.chain_config = chain_config
        self._plugin_manager = plugin_manager
        self._db_manager = create_db_manager(chain_config.database_ipc_path)
        self._db_manager.connect()  # type: ignore
        self._headerdb = self._db_manager.get_headerdb()  # type: ignore

        self._jsonrpc_ipc_path: Path = chain_config.jsonrpc_ipc_path

    @abstractmethod
    def get_chain(self) -> BaseChain:
        raise NotImplementedError("Node classes must implement this method")

    @abstractmethod
    def get_peer_pool(self) -> PeerPool:
        """
        Return the PeerPool instance of the node
        """
        raise NotImplementedError("Node classes must implement this method")

    @abstractmethod
    def get_p2p_server(self) -> BaseService:
        """
        This is the main service that will be run, when calling :meth:`run`.
        It's typically responsible for syncing the chain, with peer connections.
        """
        raise NotImplementedError("Node classes must implement this method")

    @property
    def db_manager(self) -> BaseManager:
        return self._db_manager

    @property
    def headerdb(self) -> AsyncHeaderDB:
        return self._headerdb

    def notify_resource_available(self) -> None:

        # We currently need this to give plugins the chance to start as soon
        # as the `PeerPool` is available. In the long term, the peer pool may become
        # a plugin itself and we can get rid of this.
        self._plugin_manager.broadcast(ResourceAvailableEvent(
            resource=(self.get_peer_pool(), self.cancel_token),
            resource_type=PeerPool
        ))

        # This broadcasts the *local* chain, which is suited for tasks that aren't blocking
        # for too long. There may be value in also broadcasting the proxied chain.
        self._plugin_manager.broadcast(ResourceAvailableEvent(
            resource=self.get_chain(),
            resource_type=BaseChain
        ))

    @property
    def has_ipc_server(self) -> bool:
        return bool(self._jsonrpc_ipc_path)

    def make_ipc_server(self) -> BaseService:
        if self.has_ipc_server:
            return IPCServiceWrapper(
                chain_class=self.chain_class,
                database_ipc_path=self.chain_config.database_ipc_path,
                jsonrpc_ipc_path=self.chain_config.jsonrpc_ipc_path,
                peer_pool=self.get_peer_pool(),
                token=self.cancel_token,
            )
        else:
            return None

    async def _run(self) -> None:
        if self.has_ipc_server:
            # The RPC server needs its own thread, because it provides a synchcronous
            # API which might call into p2p async methods. These sync->async calls
            # deadlock if they are run in the same Thread and loop.
            self._ipc_server = self.make_ipc_server()
            self.run_child_service(self._ipc_server)

        self.run_child_service(self.get_p2p_server())
        await self.cancel_token.wait()

    async def _cleanup(self) -> None:
        pass


def create_db_manager(ipc_path: Path) -> BaseManager:
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

    manager = DBManager(address=str(ipc_path))  # type: ignore
    return manager
