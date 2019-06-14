from abc import (
    abstractmethod,
)
from typing import (
    Any,
    Callable,
    cast,
    FrozenSet,
    Generic,
    Type,
    TypeVar,
)
from cancel_token import (
    CancelToken,
)

from p2p.exceptions import (
    PeerConnectionLost,
)
from p2p.kademlia import Node

from p2p.peer import (
    BasePeer,
    PeerSubscriber,
)
from p2p.peer_pool import (
    BasePeerPool,
)
from p2p.protocol import (
    Command,
    PayloadType,
)
from p2p.service import (
    BaseService,
)

from trinity.endpoint import (
    TrinityEventBusEndpoint,
)

from .events import (
    ConnectToNodeCommand,
    DisconnectPeerEvent,
    HasRemoteEvent,
    PeerCountRequest,
    PeerCountResponse,
    PeerJoinedEvent,
    PeerLeftEvent,
)


TPeer = TypeVar('TPeer', bound=BasePeer)
TStreamEvent = TypeVar('TStreamEvent', bound=HasRemoteEvent)


class PeerPoolEventServer(BaseService, PeerSubscriber, Generic[TPeer]):
    """
    Base class to create a bridge between the ``PeerPool`` and the event bus so that peer
    messages become available to external processes (e.g. isolated plugins). In the opposite
    direction, other processes can also retrieve information or execute actions on the peer pool by
    sending specific events through the event bus that the ``PeerPoolEventServer`` answers.

    This class bridges all common APIs but protocol specific communication can be enabled through
    subclasses that add more handlers.
    """

    msg_queue_maxsize: int = 2000

    subscription_msg_types: FrozenSet[Type[Command]] = frozenset({})

    def __init__(self,
                 event_bus: TrinityEventBusEndpoint,
                 peer_pool: BasePeerPool,
                 token: CancelToken = None) -> None:
        super().__init__(token)
        self.peer_pool = peer_pool
        self.event_bus = event_bus

    async def _run(self) -> None:
        self.logger.debug("Running %s", self.__class__.__name__)

        self.run_daemon_event(
            DisconnectPeerEvent,
            lambda peer, event: peer.disconnect_nowait(event.reason)
        )

        self.run_daemon_task(self.handle_peer_count_requests())
        self.run_daemon_task(self.handle_connect_to_node_requests())
        self.run_daemon_task(self.handle_native_peer_messages())

        await self.cancellation()

    def run_daemon_event(self,
                         event_type: Type[TStreamEvent],
                         event_handler_fn: Callable[[TPeer, TStreamEvent], Any]) -> None:
        """
        Register a handler to be run every time that an event of type ``event_type`` appears.
        """
        self.run_daemon_task(self.handle_stream(event_type, event_handler_fn))

    @abstractmethod
    async def handle_native_peer_message(self,
                                         remote: Node,
                                         cmd: Command,
                                         msg: PayloadType) -> None:
        """
        Process every native peer message. Subclasses should overwrite this to forward specific
        peer messages on the event bus. The handler is called for every message that is defined in
        ``self.subscription_msg_types``.
        """
        pass

    def get_peer(self, remote: Node) -> TPeer:
        """
        Look up and return a peer from the ``PeerPool`` that matches the given node.
        Raise ``PeerConnectionLost`` if the peer is no longer in the pool or is winding down.
        """
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

    async def handle_connect_to_node_requests(self) -> None:
        async for command in self.wait_iter(self.event_bus.stream(ConnectToNodeCommand)):
            self.logger.debug('Received request to connect to %s', command.remote)
            self.run_task(self.peer_pool.connect_to_node(command.remote))

    async def handle_peer_count_requests(self) -> None:
        async for req in self.wait_iter(self.event_bus.stream(PeerCountRequest)):
            await self.event_bus.broadcast(
                PeerCountResponse(len(self.peer_pool)),
                req.broadcast_config()
            )

    async def handle_stream(self,
                            event_type: Type[TStreamEvent],
                            event_handler_fn: Callable[[TPeer, TStreamEvent], Any]) -> None:

        async for event in self.wait_iter(self.event_bus.stream(event_type)):
            try:
                peer = self.get_peer(event.remote)
            except PeerConnectionLost:
                pass
            else:
                event_handler_fn(peer, event)

    async def handle_native_peer_messages(self) -> None:
        with self.subscribe(self.peer_pool):
            while self.is_operational:
                peer, cmd, msg = await self.wait(self.msg_queue.get())
                await self.handle_native_peer_message(peer.remote, cmd, msg)

    def register_peer(self, peer: BasePeer) -> None:
        self.logger.debug2("Broadcasting PeerJoinedEvent for %s", peer)
        self.event_bus.broadcast_nowait(PeerJoinedEvent(peer.remote))

    def deregister_peer(self, peer: BasePeer) -> None:
        self.logger.debug2("Broadcasting PeerLeftEvent for %s", peer)
        self.event_bus.broadcast_nowait(PeerLeftEvent(peer.remote))


class DefaultPeerPoolEventServer(PeerPoolEventServer[BasePeer]):

    async def handle_native_peer_message(self,
                                         remote: Node,
                                         cmd: Command,
                                         msg: PayloadType) -> None:
        pass
