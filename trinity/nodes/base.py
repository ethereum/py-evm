from abc import abstractmethod
from pathlib import Path
from multiprocessing.managers import (
    BaseManager,
)
from typing import (
    Type,
)

from eth.chains.base import BaseChain

from p2p.peer import BasePeerPool
from p2p.service import (
    BaseService,
)

from trinity.db.header import (
    AsyncHeaderDB,
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
from trinity.utils.db_proxy import (
    create_db_manager
)


class Node(BaseService):
    """
    Create usable nodes by adding subclasses that define the following
    unset attributes.
    """
    chain_class: Type[BaseChain] = None

    def __init__(self, plugin_manager: PluginManager, chain_config: ChainConfig) -> None:
        super().__init__()
        self._plugin_manager = plugin_manager
        self._db_manager = create_db_manager(chain_config.database_ipc_path)
        self._db_manager.connect()  # type: ignore
        self._headerdb = self._db_manager.get_headerdb()  # type: ignore

        self._jsonrpc_ipc_path: Path = chain_config.jsonrpc_ipc_path

    @abstractmethod
    def get_chain(self) -> BaseChain:
        raise NotImplementedError("Node classes must implement this method")

    @abstractmethod
    def get_peer_pool(self) -> BasePeerPool:
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
        peer_pool = self.get_peer_pool()
        self._plugin_manager.broadcast(ResourceAvailableEvent(
            resource=(peer_pool, self.cancel_token),
            resource_type=type(peer_pool)
        ))

        # This broadcasts the *local* chain, which is suited for tasks that aren't blocking
        # for too long. There may be value in also broadcasting the proxied chain.
        self._plugin_manager.broadcast(ResourceAvailableEvent(
            resource=self.get_chain(),
            resource_type=BaseChain
        ))

    async def _run(self) -> None:
        await self.get_p2p_server().run()
