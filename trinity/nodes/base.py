from abc import abstractmethod
from pathlib import Path
from multiprocessing.managers import (
    BaseManager,
)
from typing import (
    Type,
)

from lahja import (
    Endpoint,
    BroadcastConfig,
)

from eth.chains.base import BaseChain

from p2p.peer import BasePeerPool
from p2p.service import (
    BaseService,
)

from trinity.db.header import (
    AsyncHeaderDB,
)
from trinity.db.manager import (
    create_db_manager
)
from trinity.config import (
    TrinityConfig,
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
    chain_class: Type[BaseChain] = None

    def __init__(self, event_bus: Endpoint, trinity_config: TrinityConfig) -> None:
        super().__init__()
        self._db_manager = create_db_manager(trinity_config.database_ipc_path)
        self._db_manager.connect()
        self._headerdb = self._db_manager.get_headerdb()  # type: ignore

        self._jsonrpc_ipc_path: Path = trinity_config.jsonrpc_ipc_path
        self._network_id = trinity_config.network_id

        self.event_bus = event_bus

    async def handle_network_id_requests(self) -> None:
        async def f() -> None:
            # FIXME: There must be a way to cancel event_bus.stream() when our token is triggered,
            # but for the time being we just wrap everything in self.wait().
            async for req in self.event_bus.stream(NetworkIdRequest):
                # We are listening for all `NetworkIdRequest` events but we ensure to only send a
                # `NetworkIdResponse` to the callsite that made the request.  We do that by
                # retrieving a `BroadcastConfig` from the request via the
                # `event.broadcast_config()` API.
                self.event_bus.broadcast(
                    NetworkIdResponse(self._network_id),
                    req.broadcast_config()
                )

        await self.wait(f())

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

        self.event_bus.broadcast(
            ResourceAvailableEvent(
                resource=(peer_pool, self.cancel_token),
                resource_type=type(peer_pool)
            ),
            BroadcastConfig(internal=True),
        )

        # This broadcasts the *local* chain, which is suited for tasks that aren't blocking
        # for too long. There may be value in also broadcasting the proxied chain.
        self.event_bus.broadcast(
            ResourceAvailableEvent(
                resource=self.get_chain(),
                resource_type=BaseChain
            ),
            BroadcastConfig(internal=True),
        )

    async def _run(self) -> None:
        await self.event_bus.wait_for_connection()
        self.notify_resource_available()
        self.run_daemon_task(self.handle_network_id_requests())
        await self.get_p2p_server().run()
