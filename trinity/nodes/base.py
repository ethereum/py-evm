from abc import abstractmethod
from pathlib import Path
from multiprocessing.managers import (
    BaseManager,
)

from lahja import (
    BroadcastConfig,
)

from eth.chains.base import BaseChain

from p2p.peer_pool import BasePeerPool
from p2p.service import (
    BaseService,
)

from trinity.chains.full import FullChain
from trinity.db.eth1.header import (
    BaseAsyncHeaderDB,
)
from trinity.db.eth1.manager import (
    create_db_consumer_manager,
)
from trinity.config import (
    ChainConfig,
    TrinityConfig,
)
from trinity.endpoint import (
    TrinityEventBusEndpoint,
)
from trinity.extensibility.events import (
    ResourceAvailableEvent
)

from .events import (
    NetworkIdRequest,
    NetworkIdResponse,
)


class Node(BaseService):
    """
    Create usable nodes by adding subclasses that define the following
    unset attributes.
    """
    _full_chain: FullChain = None

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

    _chain_config: ChainConfig = None

    @property
    def chain_config(self) -> ChainConfig:
        """
        Convenience and caching mechanism for the `ChainConfig`.
        """
        if self._chain_config is None:
            self._chain_config = self.trinity_config.get_chain_config()
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

    async def notify_resource_available(self) -> None:

        # We currently need this to give plugins the chance to start as soon
        # as the `PeerPool` is available. In the long term, the peer pool may become
        # a plugin itself and we can get rid of this.
        peer_pool = self.get_peer_pool()

        await self.event_bus.broadcast(
            ResourceAvailableEvent(
                resource=(peer_pool, self.cancel_token),
                resource_type=type(peer_pool)
            ),
            BroadcastConfig(internal=True),
        )

        # This broadcasts the *local* chain, which is suited for tasks that aren't blocking
        # for too long. There may be value in also broadcasting the proxied chain.
        await self.event_bus.broadcast(
            ResourceAvailableEvent(
                resource=self.get_chain(),
                resource_type=BaseChain
            ),
            BroadcastConfig(internal=True),
        )

        # Broadcasting the DbManager internally, ensures plugins that run in the networking process
        # can reuse the existing connection instead of creating additional new connections
        await self.event_bus.broadcast(
            ResourceAvailableEvent(
                resource=self.db_manager,
                resource_type=BaseManager
            ),
            BroadcastConfig(internal=True),
        )

    async def _run(self) -> None:
        await self.event_bus.wait_until_serving()
        await self.notify_resource_available()
        self.run_daemon_task(self.handle_network_id_requests())
        self.run_daemon(self.get_p2p_server())
        await self.cancellation()

    async def _cleanup(self) -> None:
        self.event_bus.request_shutdown("Node finished unexpectedly")
