from abc import (
    abstractmethod,
)
import asyncio
import operator
from typing import (
    AsyncIterator,
    AsyncIterable,
    cast,
    Dict,
    Iterator,
    List,
    Tuple,
    Type,
)

from cancel_token import (
    CancelToken,
    OperationCancelled,
)
from eth_keys import (
    datatypes,
)
from eth_utils import (
    humanize_seconds,
)
from eth_utils.toolz import (
    groupby,
    take,
)
from lahja import (
    Endpoint,
    BroadcastConfig,
)

from p2p._utils import clamp
from p2p.constants import (
    DEFAULT_MAX_PEERS,
    DEFAULT_PEER_BOOT_TIMEOUT,
    DISCOVERY_EVENTBUS_ENDPOINT,
    MAX_CONCURRENT_CONNECTION_ATTEMPTS,
    MAX_SEQUENTIAL_PEER_CONNECT,
    PEER_CONNECT_INTERVAL,
    REQUEST_PEER_CANDIDATE_TIMEOUT,
)
from p2p.exceptions import (
    BaseP2PError,
    IneligiblePeer,
    BadAckMessage,
    HandshakeFailure,
    MalformedMessage,
    PeerConnectionLost,
    UnreachablePeer,
)
from p2p.kademlia import (
    Node,
)
from p2p.peer import (
    BasePeer,
    BasePeerFactory,
    BasePeerContext,
    handshake,
    PeerMessage,
    PeerSubscriber,
)
from p2p.peer_backend import (
    BasePeerBackend,
    DiscoveryPeerBackend,
    BootnodesPeerBackend,
)
from p2p.p2p_proto import (
    DisconnectReason,
)
from p2p.service import (
    BaseService,
)
from p2p.token_bucket import TokenBucket
from p2p.tracking.connection import (
    BaseConnectionTracker,
    NoopConnectionTracker,
)


TO_DISCOVERY_BROADCAST_CONFIG = BroadcastConfig(filter_endpoint=DISCOVERY_EVENTBUS_ENDPOINT)


COMMON_PEER_CONNECTION_EXCEPTIONS = cast(Tuple[Type[BaseP2PError], ...], (
    PeerConnectionLost,
    TimeoutError,
    UnreachablePeer,
))

# This should contain all exceptions that should not propogate during a
# standard attempt to connect to a peer.
ALLOWED_PEER_CONNECTION_EXCEPTIONS = cast(Tuple[Type[BaseP2PError], ...], (
    IneligiblePeer,
    BadAckMessage,
    MalformedMessage,
    HandshakeFailure,
)) + COMMON_PEER_CONNECTION_EXCEPTIONS


class BasePeerPool(BaseService, AsyncIterable[BasePeer]):
    """
    PeerPool maintains connections to up-to max_peers on a given network.
    """
    _report_interval = 60
    _peer_boot_timeout = DEFAULT_PEER_BOOT_TIMEOUT
    _event_bus: Endpoint = None

    def __init__(self,
                 privkey: datatypes.PrivateKey,
                 context: BasePeerContext,
                 max_peers: int = DEFAULT_MAX_PEERS,
                 token: CancelToken = None,
                 event_bus: Endpoint = None,
                 ) -> None:
        super().__init__(token)

        self.privkey = privkey
        self.max_peers = max_peers
        self.context = context

        self.connected_nodes: Dict[Node, BasePeer] = {}
        self._subscribers: List[PeerSubscriber] = []
        self._event_bus = event_bus

        # Restricts the number of concurrent connection attempts can be made
        self._connection_attempt_lock = asyncio.BoundedSemaphore(MAX_CONCURRENT_CONNECTION_ATTEMPTS)

        self.peer_backends = self.setup_peer_backends()
        self.connection_tracker = self.setup_connection_tracker()

    @property
    def has_event_bus(self) -> bool:
        return self._event_bus is not None

    def get_event_bus(self) -> Endpoint:
        if self._event_bus is None:
            raise AttributeError("No event bus configured for this peer pool")
        return self._event_bus

    def setup_connection_tracker(self) -> BaseConnectionTracker:
        """
        Return an instance of `p2p.tracking.connection.BaseConnectionTracker`
        which will be used to track peer connection failures.
        """
        return NoopConnectionTracker()

    def setup_peer_backends(self) -> Tuple[BasePeerBackend, ...]:
        if self.has_event_bus:
            return (
                DiscoveryPeerBackend(self.get_event_bus()),
                BootnodesPeerBackend(self.get_event_bus()),
            )
        else:
            self.logger.warning("No event bus configured for peer pool.")
            return ()

    async def _add_peers_from_backend(self, backend: BasePeerBackend) -> None:
        available_slots = self.max_peers - len(self)

        try:
            connected_remotes = {
                peer.remote for peer in self.connected_nodes.values()
            }
            candidates = await self.wait(
                backend.get_peer_candidates(
                    num_requested=available_slots,
                    connected_remotes=connected_remotes,
                ),
                timeout=REQUEST_PEER_CANDIDATE_TIMEOUT,
            )
        except TimeoutError:
            self.logger.warning("PeerCandidateRequest timed out to backend %s", backend)
            return
        else:
            self.logger.debug2(
                "Got candidates from backend %s (%s)",
                backend,
                candidates,
            )
            if candidates:
                await self.connect_to_nodes(iter(candidates))

    async def maybe_connect_more_peers(self) -> None:
        rate_limiter = TokenBucket(
            rate=1 / PEER_CONNECT_INTERVAL,
            capacity=MAX_SEQUENTIAL_PEER_CONNECT,
        )

        while self.is_operational:
            if self.is_full:
                await self.sleep(PEER_CONNECT_INTERVAL)
                continue

            await self.wait(rate_limiter.take())

            await self.wait(asyncio.gather(*(
                self._add_peers_from_backend(backend)
                for backend in self.peer_backends
            )))

    def __len__(self) -> int:
        return len(self.connected_nodes)

    @property
    @abstractmethod
    def peer_factory_class(self) -> Type[BasePeerFactory]:
        pass

    def get_peer_factory(self) -> BasePeerFactory:
        return self.peer_factory_class(
            privkey=self.privkey,
            context=self.context,
            event_bus=self._event_bus,
            token=self.cancel_token,
        )

    @property
    def is_full(self) -> bool:
        return len(self) >= self.max_peers

    def is_valid_connection_candidate(self, candidate: Node) -> bool:
        # connect to no more then 2 nodes with the same IP
        nodes_by_ip = groupby(
            operator.attrgetter('address.ip'),
            self.connected_nodes.keys(),
        )
        matching_ip_nodes = nodes_by_ip.get(candidate.address.ip, [])
        return len(matching_ip_nodes) <= 2

    def subscribe(self, subscriber: PeerSubscriber) -> None:
        self._subscribers.append(subscriber)
        for peer in self.connected_nodes.values():
            subscriber.register_peer(peer)
            peer.add_subscriber(subscriber)

    def unsubscribe(self, subscriber: PeerSubscriber) -> None:
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)
        for peer in self.connected_nodes.values():
            peer.remove_subscriber(subscriber)

    async def start_peer(self, peer: BasePeer) -> None:
        self.run_child_service(peer)
        await self.wait(peer.events.started.wait(), timeout=1)
        if peer.is_operational:
            self._add_peer(peer, ())
        else:
            self.logger.debug("%s was cancelled immediately, not adding to pool", peer)

        try:
            await self.wait(
                peer.boot_manager.events.finished.wait(),
                timeout=self._peer_boot_timeout
            )
        except TimeoutError as err:
            self.logger.debug('Timout waiting for peer to boot: %s', err)
            await peer.disconnect(DisconnectReason.timeout)
            return
        except HandshakeFailure as err:
            await self.connection_tracker.record_failure(peer.remote, err)
            raise
        else:
            if not peer.is_operational:
                self.logger.debug('%s disconnected during boot-up, dropped from pool', peer)

    def _add_peer(self,
                  peer: BasePeer,
                  msgs: Tuple[PeerMessage, ...]) -> None:
        """Add the given peer to the pool.

        Appart from adding it to our list of connected nodes and adding each of our subscriber's
        to the peer, we also add the given messages to our subscriber's queues.
        """
        self.logger.info('Adding %s to pool', peer)
        self.connected_nodes[peer.remote] = peer
        peer.add_finished_callback(self._peer_finished)
        for subscriber in self._subscribers:
            subscriber.register_peer(peer)
            peer.add_subscriber(subscriber)
            for msg in msgs:
                subscriber.add_msg(msg)

    async def _run(self) -> None:
        # FIXME: PeerPool should probably no longer be a BaseService, but for now we're keeping it
        # so in order to ensure we cancel all peers when we terminate.
        if self.has_event_bus:
            self.run_daemon_task(self.maybe_connect_more_peers())

        self.run_daemon_task(self._periodically_report_stats())
        await self.cancel_token.wait()

    async def stop_all_peers(self) -> None:
        self.logger.info("Stopping all peers ...")
        peers = self.connected_nodes.values()
        await asyncio.gather(*(
            peer.disconnect(DisconnectReason.client_quitting)
            for peer in peers
            if peer.is_running
        ))

    async def _cleanup(self) -> None:
        await self.stop_all_peers()

    async def connect(self, remote: Node) -> BasePeer:
        """
        Connect to the given remote and return a Peer instance when successful.
        Returns None if the remote is unreachable, times out or is useless.
        """
        if remote in self.connected_nodes:
            self.logger.debug2("Skipping %s; already connected to it", remote)
            raise IneligiblePeer(f"Already connected to {remote}")

        try:
            should_connect = await self.wait(
                self.connection_tracker.should_connect_to(remote),
                timeout=1,
            )
        except TimeoutError:
            self.logger.warning("ConnectionTracker.should_connect_to request timed out.")
            raise

        if not should_connect:
            raise IneligiblePeer(f"Peer database rejected peer candidate: {remote}")

        try:
            self.logger.debug2("Connecting to %s...", remote)
            # We use self.wait() as well as passing our CancelToken to handshake() as a workaround
            # for https://github.com/ethereum/py-evm/issues/670.
            peer = await self.wait(handshake(remote, self.get_peer_factory()))

            return peer
        except OperationCancelled:
            # Pass it on to instruct our main loop to stop.
            raise
        except BadAckMessage:
            # This is kept separate from the
            # `COMMON_PEER_CONNECTION_EXCEPTIONS` to be sure that we aren't
            # silencing an error in our authentication code.
            self.logger.error('Got bad auth ack from %r', remote)
            # dump the full stacktrace in the debug logs
            self.logger.debug('Got bad auth ack from %r', remote, exc_info=True)
            raise
        except MalformedMessage:
            # This is kept separate from the
            # `COMMON_PEER_CONNECTION_EXCEPTIONS` to be sure that we aren't
            # silencing an error in how we decode messages during handshake.
            self.logger.error('Got malformed response from %r during handshake', remote)
            # dump the full stacktrace in the debug logs
            self.logger.debug('Got malformed response from %r', remote, exc_info=True)
            raise
        except HandshakeFailure as e:
            self.logger.debug("Could not complete handshake with %r: %s", remote, repr(e))
            await self.connection_tracker.record_failure(remote, e)
            raise
        except COMMON_PEER_CONNECTION_EXCEPTIONS as e:
            self.logger.debug("Could not complete handshake with %r: %s", remote, repr(e))
            raise
        except Exception:
            self.logger.exception("Unexpected error during auth/p2p handshake with %r", remote)
            raise

    async def connect_to_nodes(self, nodes: Iterator[Node]) -> None:
        # create an generator for the nodes
        nodes_iter = iter(nodes)

        while True:
            if self.is_full or not self.is_operational:
                return

            # only attempt to connect to up to the maximum number of available
            # peer slots that are open.
            available_peer_slots = self.max_peers - len(self)
            batch_size = clamp(1, 10, available_peer_slots)
            batch = tuple(take(batch_size, nodes_iter))

            # There are no more *known* nodes to connect to.
            if not batch:
                return

            self.logger.debug(
                'Initiating %d peer connection attempts with %d open peer slots',
                len(batch),
                available_peer_slots,
            )
            # Try to connect to the peers concurrently.
            await self.wait(asyncio.gather(
                *(self.connect_to_node(node) for node in batch),
                loop=self.get_event_loop(),
            ))

    async def connect_to_node(self, node: Node) -> None:
        """
        Connect to a single node quietly aborting if the peer pool is full or
        shutting down, or one of the expected peer level exceptions is raised
        while connecting.
        """
        if self.is_full or not self.is_operational:
            return

        try:
            async with self._connection_attempt_lock:
                peer = await self.connect(node)
        except ALLOWED_PEER_CONNECTION_EXCEPTIONS:
            return

        # Check again to see if we have *become* full since the previous
        # check.
        if self.is_full:
            self.logger.debug(
                "Successfully connected to %s but peer pool is full.  Disconnecting.",
                peer,
            )
            await peer.disconnect(DisconnectReason.too_many_peers)
            return
        elif not self.is_operational:
            self.logger.debug(
                "Successfully connected to %s but peer pool no longer operational.  Disconnecting.",
                peer,
            )
            await peer.disconnect(DisconnectReason.client_quitting)
            return
        else:
            await self.start_peer(peer)

    def _peer_finished(self, peer: BaseService) -> None:
        """
        Remove the given peer from our list of connected nodes.
        This is passed as a callback to be called when a peer finishes.
        """
        peer = cast(BasePeer, peer)
        if peer.remote in self.connected_nodes:
            self.logger.info("%s finished[%s], removing from pool", peer, peer.disconnect_reason)
            self.connected_nodes.pop(peer.remote)
        else:
            self.logger.warning(
                "%s finished but was not found in connected_nodes (%s)",
                peer,
                tuple(sorted(self.connected_nodes.values())),
            )

        for subscriber in self._subscribers:
            subscriber.deregister_peer(peer)

    async def __aiter__(self) -> AsyncIterator[BasePeer]:
        for peer in tuple(self.connected_nodes.values()):
            # Yield control to ensure we process any disconnection requests from peers. Otherwise
            # we could return peers that should have been disconnected already.
            await asyncio.sleep(0)
            if not peer.is_closing:
                yield peer

    async def _periodically_report_stats(self) -> None:
        while self.is_operational:
            inbound_peers = len(
                [peer for peer in self.connected_nodes.values() if peer.inbound])
            self.logger.info("Connected peers: %d inbound, %d outbound",
                             inbound_peers, (len(self.connected_nodes) - inbound_peers))
            subscribers = len(self._subscribers)
            if subscribers:
                longest_queue = max(
                    self._subscribers, key=operator.attrgetter('queue_size'))
                self.logger.info(
                    "Peer subscribers: %d, longest queue: %s(%d)",
                    subscribers, longest_queue.__class__.__name__, longest_queue.queue_size)

            self.logger.debug("== Peer details == ")
            for peer in self.connected_nodes.values():
                if not peer.is_running:
                    self.logger.warning(
                        "%s is no longer alive but has not been removed from pool", peer)
                    continue
                most_received_type, count = max(
                    peer.received_msgs.items(), key=operator.itemgetter(1))
                self.logger.debug(
                    "%s: uptime=%s, received_msgs=%d, most_received=%s(%d)",
                    peer, humanize_seconds(peer.uptime), peer.received_msgs_count,
                    most_received_type, count)
                self.logger.debug("client_version_string='%s'", peer.client_version_string)
                for line in peer.get_extra_stats():
                    self.logger.debug("    %s", line)
            self.logger.debug("== End peer details == ")
            await self.sleep(self._report_interval)
