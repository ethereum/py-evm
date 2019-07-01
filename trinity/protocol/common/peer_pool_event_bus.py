from abc import (
    abstractmethod,
)
from typing import (
    Any,
    AsyncIterator,
    Callable,
    cast,
    Dict,
    FrozenSet,
    Generic,
    Tuple,
    Type,
    TypeVar,
)
from cancel_token import (
    CancelToken,
)

from lahja import (
    BaseEvent,
    BaseRequestResponseEvent,
    BroadcastConfig,
)

from p2p.exceptions import (
    PeerConnectionLost,
)
from p2p.kademlia import (
    Node,
)
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
    GetConnectedPeersRequest,
    GetConnectedPeersResponse,
    PeerCountRequest,
    PeerCountResponse,
    PeerJoinedEvent,
    PeerLeftEvent,
)
from .peer import (
    BaseProxyPeer,
)


TPeer = TypeVar('TPeer', bound=BasePeer)
TEvent = TypeVar('TEvent', bound=BaseEvent)
TRequest = TypeVar('TRequest', bound=BaseRequestResponseEvent[Any])


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
            lambda event: self.try_with_node(
                event.remote,
                lambda peer: peer.disconnect_nowait(event.reason)
            )
        )

        self.run_daemon_task(self.handle_peer_count_requests())
        self.run_daemon_task(self.handle_connect_to_node_requests())
        self.run_daemon_task(self.handle_native_peer_messages())
        self.run_daemon_task(self.handle_get_connected_peers_requests())

        await self.cancellation()

    def run_daemon_event(self,
                         event_type: Type[TEvent],
                         event_handler_fn: Callable[[TEvent], Any]) -> None:
        """
        Register a handler to be run every time that an event of type ``event_type`` appears.
        """
        self.run_daemon_task(self.handle_stream(event_type, event_handler_fn))

    def run_daemon_request(
            self,
            event_type: Type[TRequest],
            event_handler_fn: Callable[[TRequest], Any]) -> None:
        """
        Register a handler to be run every time that an request of type ``event_type`` appears.
        """
        self.run_daemon_task(self.handle_request_stream(event_type, event_handler_fn))

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

    async def handle_get_connected_peers_requests(self) -> None:
        async for req in self.wait_iter(self.event_bus.stream(GetConnectedPeersRequest)):
            await self.event_bus.broadcast(
                GetConnectedPeersResponse(tuple(self.peer_pool.connected_nodes.keys())),
                req.broadcast_config()
            )

    async def handle_stream(self,
                            event_type: Type[TEvent],
                            event_handler_fn: Callable[[TEvent], Any]) -> None:

        async for event in self.wait_iter(self.event_bus.stream(event_type)):
            await event_handler_fn(event)

    async def handle_request_stream(
            self,
            event_type: Type[TRequest],
            event_handler_fn: Callable[[TRequest], Any]) -> None:

        async for event in self.wait_iter(self.event_bus.stream(event_type)):
            try:
                self.logger.debug2("Replaying %s request on actual peer", event_type)
                val = await event_handler_fn(event)
            except Exception as e:
                await self.event_bus.broadcast(
                    event.expected_response_type()(None, e),
                    event.broadcast_config()
                )
            else:
                self.logger.debug2(
                    "Forwarding response to %s from peer to its proxy peer",
                    event_type,
                )
                await self.event_bus.broadcast(
                    event.expected_response_type()(val, None),
                    event.broadcast_config()
                )

    async def try_with_node(self, remote: Node, fn: Callable[[TPeer], Any]) -> None:
        try:
            peer = self.get_peer(remote)
        except PeerConnectionLost:
            pass
        else:
            fn(peer)

    async def with_node_and_timeout(self,
                                    remote: Node,
                                    timeout: float,
                                    fn: Callable[[TPeer], Any]) -> Any:
        peer = self.get_peer(remote)
        return await self.wait(fn(peer), timeout=timeout)

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


TProxyPeer = TypeVar('TProxyPeer', bound=BaseProxyPeer)


class BaseProxyPeerPool(BaseService, Generic[TProxyPeer]):
    """
    Base class for peer pools that can be used from any process instead of the actual peer pool
    that runs in another process. Eventually, every process that needs to interact with the peer
    pool should be able to use a proxy peer pool for all peer pool interactions.
    """

    def __init__(self,
                 event_bus: TrinityEventBusEndpoint,
                 broadcast_config: BroadcastConfig,
                 token: CancelToken=None):
        super().__init__(token)
        self.event_bus = event_bus
        self.broadcast_config = broadcast_config
        self.connected_peers: Dict[Node, TProxyPeer] = dict()

    async def stream_existing_and_joining_peers(self) -> AsyncIterator[TProxyPeer]:
        for proxy_peer in await self.get_peers():
            yield proxy_peer

        async for new_proxy_peer in self.wait_iter(self.stream_peers_joining()):
            yield new_proxy_peer

    # TODO: PeerJoinedEvent/PeerLeftEvent should probably include a session id
    async def stream_peers_joining(self) -> AsyncIterator[TProxyPeer]:
        async for ev in self.wait_iter(self.event_bus.stream(PeerJoinedEvent)):
            yield await self.ensure_proxy_peer(ev.remote)

    async def handle_joining_peers(self) -> None:
        async for peer in self.wait_iter(self.stream_peers_joining()):
            # We just want to consume the AsyncIterator
            self.logger.info("New Proxy Peer joined %s", peer)

    async def handle_leaving_peers(self) -> None:
        async for ev in self.wait_iter(self.event_bus.stream(PeerLeftEvent)):
            if ev.remote not in self.connected_peers:
                self.logger.warning("Wanted to remove peer but it is missing %s", ev.remote)
            else:
                proxy_peer = self.connected_peers.pop(ev.remote)
                # TODO: Double check based on some session id if we are indeed
                # removing the right peer
                await proxy_peer.cancel()
                self.logger.warning("Removed proxy peer from proxy pool %s", ev.remote)

    async def fetch_initial_peers(self) -> Tuple[TProxyPeer, ...]:
        response = await self.wait(
            self.event_bus.request(GetConnectedPeersRequest(), self.broadcast_config)
        )

        return tuple([await self.ensure_proxy_peer(remote) for remote in response.remotes])

    async def get_peers(self) -> Tuple[TProxyPeer, ...]:
        """
        Return proxy peer objects for all connected peers in the actual pool.
        """

        # The ProxyPeerPool could be started at any point in time after the actual peer pool.
        # Based on this assumption, if we don't have any proxy peers yet, sync with the actual pool
        # first. From that point on, the proxy peer pool will maintain the set of proxies based on
        # the events of incoming / leaving peers.
        if not any(self.connected_peers):
            await self.fetch_initial_peers()
        return tuple(self.connected_peers.values())

    @abstractmethod
    def convert_node_to_proxy_peer(self,
                                   remote: Node,
                                   event_bus: TrinityEventBusEndpoint,
                                   broadcast_config: BroadcastConfig) -> TProxyPeer:
        pass

    async def ensure_proxy_peer(self, remote: Node) -> TProxyPeer:

        if remote not in self.connected_peers:
            proxy_peer = self.convert_node_to_proxy_peer(
                remote,
                self.event_bus,
                self.broadcast_config
            )
            self.connected_peers[remote] = proxy_peer
            self.run_child_service(proxy_peer)
            await proxy_peer.events.started.wait()

        return self.connected_peers[remote]

    async def _run(self) -> None:
        self.run_daemon_task(self.handle_joining_peers())
        self.run_daemon_task(self.handle_leaving_peers())
        await self.cancellation()
