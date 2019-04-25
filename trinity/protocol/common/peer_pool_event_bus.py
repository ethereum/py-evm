from typing import (
    cast,
    Generic,
    TypeVar,
)
from cancel_token import (
    CancelToken,
)
from lahja import (
    Endpoint,
)

from p2p.exceptions import (
    PeerConnectionLost,
)
from p2p.kademlia import Node
from p2p.peer import (
    BasePeer,
)
from p2p.peer_pool import (
    BasePeerPool,
)
from p2p.service import (
    BaseService,
)

from .events import (
    ConnectToNodeCommand,
    DisconnectPeerEvent,
    PeerCountRequest,
    PeerCountResponse,
)


TPeer = TypeVar('TPeer', bound=BasePeer)


class PeerPoolEventServer(BaseService, Generic[TPeer]):
    """
    Base request handler that listens for requests on the event bus that should be delegated to
    the peer pool to either perform an action or return some response. Subclasses should extend
    this class with custom event handlers.
    """

    def __init__(self,
                 event_bus: Endpoint,
                 peer_pool: BasePeerPool,
                 token: CancelToken = None) -> None:
        super().__init__(token)
        self.peer_pool = peer_pool
        self.event_bus = event_bus

    async def accept_connect_commands(self) -> None:
        async for command in self.wait_iter(self.event_bus.stream(ConnectToNodeCommand)):
            self.logger.debug('Received request to connect to %s', command.remote)
            self.run_task(self.peer_pool.connect_to_node(command.remote))

    async def handle_peer_count_requests(self) -> None:
        async for req in self.wait_iter(self.event_bus.stream(PeerCountRequest)):
            await self.event_bus.broadcast(
                PeerCountResponse(len(self.peer_pool)),
                req.broadcast_config()
            )

    async def handle_disconnect_peer_events(self) -> None:
        async for command in self.wait_iter(self.event_bus.stream(DisconnectPeerEvent)):
            try:
                peer = self.get_peer(command.remote)
            except PeerConnectionLost:
                pass
            else:
                peer.disconnect(command.reason)

    async def _run(self) -> None:
        self.logger.debug("Running PeerPoolEventServer")

        self.run_daemon_task(self.handle_peer_count_requests())
        self.run_daemon_task(self.accept_connect_commands())
        self.run_daemon_task(self.handle_disconnect_peer_events())

        await self.cancel_token.wait()

    def get_peer(self, remote: Node) -> TPeer:

        try:
            peer = self.peer_pool.connected_nodes[remote]
        except KeyError:
            self.logger.debug("Peer with remote %s does not exist in the pool anymore", remote)
            raise PeerConnectionLost()
        else:
            if not peer.is_operational:
                self.logger.debug("Peer %s is not operational when selecting from pool", peer)
                raise PeerConnectionLost()
            else:
                return cast(TPeer, peer)


DefaultPeerPoolEventBusRequestHandler = PeerPoolEventServer[BasePeer]
