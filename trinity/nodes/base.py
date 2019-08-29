from abc import abstractmethod
from pathlib import Path
from typing import (
    Generic,
    TypeVar,
)

from lahja import EndpointAPI

from eth.abc import (
    AtomicDatabaseAPI,
    ChainAPI,
)

from p2p.peer_pool import BasePeerPool
from p2p.service import (
    BaseService,
)

from trinity.chains.full import FullChain
from trinity.db.manager import DBClient
from trinity.db.eth1.header import (
    AsyncHeaderDB,
    BaseAsyncHeaderDB,
)
from trinity.events import ShutdownRequest
from trinity.config import (
    Eth1ChainConfig,
    Eth1AppConfig,
    TrinityConfig,
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

    def __init__(self, event_bus: EndpointAPI, trinity_config: TrinityConfig) -> None:
        super().__init__()
        self.trinity_config = trinity_config
        self._base_db = DBClient.connect(trinity_config.database_ipc_path)
        self._headerdb = AsyncHeaderDB(self._base_db)

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
    def get_chain(self) -> ChainAPI:
        ...

    def get_full_chain(self) -> FullChain:
        if self._full_chain is None:
            chain_class = self.chain_config.full_chain_class
            self._full_chain = chain_class(self._base_db)

        return self._full_chain

    @abstractmethod
    def get_event_server(self) -> PeerPoolEventServer[TPeer]:
        """
        Return the ``PeerPoolEventServer`` of the node
        """
        ...

    @abstractmethod
    def get_peer_pool(self) -> BasePeerPool:
        """
        Return the PeerPool instance of the node
        """
        ...

    @abstractmethod
    def get_p2p_server(self) -> BaseService:
        """
        This is the main service that will be run, when calling :meth:`run`.
        It's typically responsible for syncing the chain, with peer connections.
        """
        ...

    @property
    def base_db(self) -> AtomicDatabaseAPI:
        return self._base_db

    @property
    def headerdb(self) -> BaseAsyncHeaderDB:
        return self._headerdb

    async def _run(self) -> None:
        self.run_daemon_task(self.handle_network_id_requests())
        self.run_daemon(self.get_p2p_server())
        self.run_daemon(self.get_event_server())
        await self.cancellation()

    async def _cleanup(self) -> None:
        await self.event_bus.broadcast(ShutdownRequest("Node finished unexpectedly"))
