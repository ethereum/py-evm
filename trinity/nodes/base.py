from abc import abstractmethod
from pathlib import Path
from multiprocessing.managers import (
    BaseManager,
)
from typing import (
    Generic,
    TypeVar,
)

from eth.chains.base import BaseChain

from p2p.peer_pool import BasePeerPool
from p2p.service import (
    BaseService,
)
from p2p._utils import ensure_global_asyncio_executor

from trinity.chains.full import FullChain
from trinity.db.eth1.header import (
    BaseAsyncHeaderDB,
)
from trinity.db.eth1.manager import (
    create_db_consumer_manager,
)
from trinity.config import (
    Eth1ChainConfig,
    Eth1AppConfig,
    TrinityConfig,
)
from trinity.endpoint import (
    TrinityEventBusEndpoint,
)
from trinity.protocol.common.peer import BasePeer
from trinity.protocol.common.peer_pool_event_bus import (
    PeerPoolEventServer,
)

from .events import (
    NetworkIdRequest,
    NetworkIdResponse,
)

TPeer = TypeVar('TPeer', bound=BasePeer)


class Node(BaseService, Generic[TPeer]):
    """
    Create usable nodes by adding subclasses that define the following
    unset attributes.
    """
    _full_chain: FullChain = None
    _event_server: PeerPoolEventServer[TPeer] = None

    def __init__(self, event_bus: TrinityEventBusEndpoint, trinity_config: TrinityConfig) -> None:
        super().__init__()
        self.trinity_config = trinity_config
        self._db_manager = create_db_consumer_manager(trinity_config.database_ipc_path)
        self._headerdb = self._db_manager.get_headerdb()  # type: ignore

        self._jsonrpc_ipc_path: Path = trinity_config.jsonrpc_ipc_path
        self._network_id = trinity_config.network_id

        self.event_bus = event_bus

    async def handle_network_id_requests(self) -> None:
        async for req in self.wait_iter(self.event_bus.stream(NetworkIdRequest)):
            # We are listening for all `NetworkIdRequest` events but we ensure to only send a
            # `NetworkIdResponse` to the callsite that made the request.  We do that by
            # retrieving a `BroadcastConfig` from the request via the
            # `event.broadcast_config()` API.
            await self.event_bus.broadcast(
                NetworkIdResponse(self._network_id),
                req.broadcast_config()
            )

    _chain_config: Eth1ChainConfig = None

    @property
    def chain_config(self) -> Eth1ChainConfig:
        """
        Convenience and caching mechanism for the `ChainConfig`.
        """
        if self._chain_config is None:
            app_config = self.trinity_config.get_app_config(Eth1AppConfig)
            self._chain_config = app_config.get_chain_config()
        return self._chain_config

    @abstractmethod
    def get_chain(self) -> BaseChain:
        raise NotImplementedError("Node classes must implement this method")

    def get_full_chain(self) -> FullChain:
        if self._full_chain is None:
            chain_class = self.chain_config.full_chain_class
            self._full_chain = chain_class(self.db_manager.get_db())  # type: ignore

        return self._full_chain

    @abstractmethod
    def get_event_server(self) -> PeerPoolEventServer[TPeer]:
        """
        Return the ``PeerPoolEventServer`` of the node
        """
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
    def headerdb(self) -> BaseAsyncHeaderDB:
        return self._headerdb

    async def _run(self) -> None:
        # The `networking` process creates a process pool executor to offload cpu intensive
        # tasks. We should revisit that when we move the sync in its own process
        ensure_global_asyncio_executor()
        self.run_daemon_task(self.handle_network_id_requests())
        self.run_daemon(self.get_p2p_server())
        self.run_daemon(self.get_event_server())
        await self.cancellation()

    async def _cleanup(self) -> None:
        self.event_bus.request_shutdown("Node finished unexpectedly")
        ensure_global_asyncio_executor().shutdown(wait=True)
