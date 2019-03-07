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
from eth_utils.toolz import (
    groupby,
)
from lahja import (
    Endpoint,
)

from p2p.constants import (
    DEFAULT_MAX_PEERS,
    DEFAULT_PEER_BOOT_TIMEOUT,
    DISOVERY_INTERVAL,
    REQUEST_PEER_CANDIDATE_TIMEOUT,
)
from p2p.events import (
    ConnectToNodeCommand,
    PeerCandidatesRequest,
    PeerCountRequest,
    PeerCountResponse,
    RandomBootnodeRequest,
)
from p2p.exceptions import (
    BadAckMessage,
    HandshakeFailure,
    MalformedMessage,
    PeerConnectionLost,
    UnreachablePeer,
)
from p2p.kademlia import (
    from_uris,
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
from p2p.persistence import (
    BasePeerInfo,
    NoopPeerInfo,
)
from p2p.p2p_proto import (
    DisconnectReason,
)
from p2p.service import (
    BaseService,
)


class BasePeerPool(BaseService, AsyncIterable[BasePeer]):
    """
    PeerPool maintains connections to up-to max_peers on a given network.
    """
    _report_interval = 60
    _peer_boot_timeout = DEFAULT_PEER_BOOT_TIMEOUT

    def __init__(self,
                 privkey: datatypes.PrivateKey,
                 context: BasePeerContext,
                 max_peers: int = DEFAULT_MAX_PEERS,
                 peer_info: BasePeerInfo = NoopPeerInfo(),
                 token: CancelToken = None,
                 event_bus: Endpoint = None
                 ) -> None:
        super().__init__(token)

        self.peer_info = peer_info

        self.privkey = privkey
        self.max_peers = max_peers
        self.context = context

        self.connected_nodes: Dict[Node, BasePeer] = {}
        self._subscribers: List[PeerSubscriber] = []
        self.event_bus = event_bus

    async def accept_connect_commands(self) -> None:
        async for command in self.wait_iter(self.event_bus.stream(ConnectToNodeCommand)):
            self.logger.debug('Received request to connect to %s', command.node)
            self.run_task(self.connect_to_nodes(from_uris([command.node])))

    async def handle_peer_count_requests(self) -> None:
        async for req in self.wait_iter(self.event_bus.stream(PeerCountRequest)):
                # We are listening for all `PeerCountRequest` events but we ensure to only send a
                # `PeerCountResponse` to the callsite that made the request.  We do that by
                # retrieving a `BroadcastConfig` from the request via the
                # `event.broadcast_config()` API.
                self.event_bus.broadcast(PeerCountResponse(len(self)), req.broadcast_config())

    async def maybe_connect_more_peers(self) -> None:
        while self.is_operational:
            await self.sleep(DISOVERY_INTERVAL)

            available_peer_slots = self.max_peers - len(self)
            if available_peer_slots > 0:
                try:
                    response = await self.wait(
                        # TODO: This should use a BroadcastConfig to send the request to discovery
                        # only as soon as we have cut a new Lahja release.
                        self.event_bus.request(PeerCandidatesRequest(available_peer_slots)),
                        timeout=REQUEST_PEER_CANDIDATE_TIMEOUT
                    )
                except TimeoutError:
                    self.logger.warning("Discovery did not answer PeerCandidateRequest in time")
                    continue

                # In some cases (e.g ROPSTEN or private testnets), the discovery table might be
                # full of bad peers so if we can't connect to any peers we try a random bootstrap
                # node as well.
                if not len(self):
                    try:
                        response = await self.wait(
                            # TODO: This should use a BroadcastConfig to send the request to
                            # discovery only as soon as we have cut a new Lahja release.
                            self.event_bus.request(RandomBootnodeRequest()),
                            timeout=REQUEST_PEER_CANDIDATE_TIMEOUT
                        )
                    except TimeoutError:
                        self.logger.warning(
                            "Discovery did not answer RandomBootnodeRequest in time"
                        )
                        continue

                self.logger.debug2("Received candidates to connect to (%s)", response.candidates)
                await self.connect_to_nodes(from_uris(response.candidates))

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
            token=self.cancel_token,
        )

    @property
    def is_full(self) -> bool:
        return len(self) >= self.max_peers

    def is_valid_connection_candidate(self, candidate: Node) -> bool:
        # connect to no more then 2 nodes with the same IP
        nodes_by_ip = groupby(
            operator.attrgetter('remote.address.ip'),
            self.connected_nodes.values(),
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
        try:
            with peer.collect_sub_proto_messages() as buffer:
                await self.wait(
                    peer.boot_manager.events.finished.wait(),
                    timeout=self._peer_boot_timeout
                )
        except TimeoutError as err:
            self.logger.debug('Timout waiting for peer to boot: %s', err)
            await peer.disconnect(DisconnectReason.timeout)
            return
        else:
            if peer.is_operational:
                self._add_peer(peer, buffer.get_messages())
            else:
                self.logger.debug('%s disconnected during boot-up, not adding to pool', peer)

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
        if self.event_bus is not None:
            self.run_daemon_task(self.handle_peer_count_requests())
            self.run_daemon_task(self.maybe_connect_more_peers())
            self.run_daemon_task(self.accept_connect_commands())
        self.run_daemon_task(self._periodically_report_stats())
        await self.cancel_token.wait()

    async def stop_all_peers(self) -> None:
        self.logger.info("Stopping all peers ...")
        peers = self.connected_nodes.values()
        await asyncio.gather(*[
            peer.disconnect(DisconnectReason.client_quitting) for peer in peers if peer.is_running
        ])

    async def _cleanup(self) -> None:
        await self.stop_all_peers()

    async def connect(self, remote: Node) -> BasePeer:
        """
        Connect to the given remote and return a Peer instance when successful.
        Returns None if the remote is unreachable, times out or is useless.
        """
        if remote in self.connected_nodes:
            self.logger.debug("Skipping %s; already connected to it", remote)
            return None
        if not self.peer_info.should_connect_to(remote):
            return None
        expected_exceptions = (
            PeerConnectionLost,
            TimeoutError,
            UnreachablePeer,
        )
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
            # This is kept separate from the `expected_exceptions` to be sure that we aren't
            # silencing an error in our authentication code.
            self.logger.error('Got bad auth ack from %r', remote)
            # dump the full stacktrace in the debug logs
            self.logger.debug('Got bad auth ack from %r', remote, exc_info=True)
        except MalformedMessage:
            # This is kept separate from the `expected_exceptions` to be sure that we aren't
            # silencing an error in how we decode messages during handshake.
            self.logger.error('Got malformed response from %r during handshake', remote)
            # dump the full stacktrace in the debug logs
            self.logger.debug('Got malformed response from %r', remote, exc_info=True)
        except HandshakeFailure as e:
            self.logger.debug("Could not complete handshake with %r: %s", remote, repr(e))
            self.peer_info.record_failure(remote, e)
        except expected_exceptions as e:
            self.logger.debug("Could not complete handshake with %r: %s", remote, repr(e))
        except Exception:
            self.logger.exception("Unexpected error during auth/p2p handshake with %r", remote)
        return None

    async def connect_to_nodes(self, nodes: Iterator[Node]) -> None:
        for node in nodes:
            if self.is_full or not self.is_operational:
                return

            # TODO: Consider changing connect() to raise an exception instead of returning None,
            # as discussed in
            # https://github.com/ethereum/py-evm/pull/139#discussion_r152067425
            peer = await self.connect(node)
            if peer is not None:
                await self.start_peer(peer)

    def _peer_finished(self, peer: BaseService) -> None:
        """Remove the given peer from our list of connected nodes.
        This is passed as a callback to be called when a peer finishes.
        """
        peer = cast(BasePeer, peer)
        if peer.remote in self.connected_nodes:
            self.logger.info("%s finished, removing from pool", peer)
            self.connected_nodes.pop(peer.remote)
        else:
            self.logger.warning(
                "%s finished but was not found in connected_nodes (%s)", peer, self.connected_nodes)
        for subscriber in self._subscribers:
            subscriber.deregister_peer(peer)

    def __aiter__(self) -> AsyncIterator[BasePeer]:
        return ConnectedPeersIterator(tuple(self.connected_nodes.values()))

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
                    peer, peer.uptime, peer.received_msgs_count,
                    most_received_type, count)
                self.logger.debug("client_version_string='%s'", peer.client_version_string)
                for line in peer.get_extra_stats():
                    self.logger.debug("    %s", line)
            self.logger.debug("== End peer details == ")
            await self.sleep(self._report_interval)


class ConnectedPeersIterator(AsyncIterator[BasePeer]):

    def __init__(self, peers: Tuple[BasePeer, ...]) -> None:
        self.iter = iter(peers)

    async def __anext__(self) -> BasePeer:
        while True:
            # Yield control to ensure we process any disconnection requests from peers. Otherwise
            # we could return peers that should have been disconnected already.
            await asyncio.sleep(0)
            try:
                peer = next(self.iter)
                if not peer.is_closing:
                    return peer
            except StopIteration:
                raise StopAsyncIteration
