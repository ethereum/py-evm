"""
The Node Discovery protocol provides a way to find RLPx nodes that can be connected to. It uses a
Kademlia-like protocol to maintain a distributed database of the IDs and endpoints of all
listening nodes.

More information at https://github.com/ethereum/devp2p/blob/master/rlpx.md#node-discovery
"""
import asyncio
import collections
import contextlib
import random
import socket
import time
from typing import (
    Any,
    Callable,
    cast,
    DefaultDict,
    Dict,
    Hashable,
    Iterable,
    Iterator,
    List,
    Sequence,
    Set,
    Text,
    Tuple,
    TYPE_CHECKING,
    Union,
)

import eth_utils.toolz
from eth_utils import (
    ExtendedDebugLogger,
    get_extended_debug_logger,
)

from lahja import (
    EndpointAPI,
)

import rlp

from eth_typing import Hash32

from eth_utils import (
    encode_hex,
    to_bytes,
    to_hex,
    to_list,
    to_tuple,
    int_to_big_endian,
    big_endian_to_int,
)

from eth_keys import keys
from eth_keys import datatypes

from eth_hash.auto import keccak

from cancel_token import CancelToken, OperationCancelled

from p2p import constants
from p2p.abc import AddressAPI, NodeAPI
from p2p.events import (
    PeerCandidatesRequest,
    RandomBootnodeRequest,
    BaseRequestResponseEvent,
    PeerCandidatesResponse,
)
from p2p.exceptions import AlreadyWaitingDiscoveryResponse, NoEligibleNodes
from p2p.kademlia import Address, Node, RoutingTable, check_relayed_addr, sort_by_distance
from p2p.service import BaseService

if TYPE_CHECKING:
    # Promoted workaround for inheriting from generic stdlib class
    # https://github.com/python/mypy/issues/5264#issuecomment-399407428
    UserDict = collections.UserDict[Hashable, 'CallbackLock']
else:
    UserDict = collections.UserDict

# V4 handler methods take a Node, payload and msg_hash as arguments.
V4_HANDLER_TYPE = Callable[[NodeAPI, Tuple[Any, ...], Hash32], None]

MAX_ENTRIES_PER_TOPIC = 50
# UDP packet constants.
MAC_SIZE = 256 // 8  # 32
SIG_SIZE = 520 // 8  # 65
HEAD_SIZE = MAC_SIZE + SIG_SIZE  # 97
EXPIRATION = 60  # let messages expire after N secondes
PROTO_VERSION = 4


class DefectiveMessage(Exception):
    pass


class WrongMAC(DefectiveMessage):
    pass


class UnknownCommand(DefectiveMessage):
    pass


class DiscoveryCommand:
    def __init__(self, name: str, id: int, elem_count: int) -> None:
        self.name = name
        self.id = id
        # Number of required top-level list elements for this cmd.
        # Elements beyond this length must be trimmed.
        self.elem_count = elem_count

    def __repr__(self) -> str:
        return 'Command(%s:%d)' % (self.name, self.id)


CMD_PING = DiscoveryCommand("ping", 1, 4)
CMD_PONG = DiscoveryCommand("pong", 2, 3)
CMD_FIND_NODE = DiscoveryCommand("find_node", 3, 2)
CMD_NEIGHBOURS = DiscoveryCommand("neighbours", 4, 2)
CMD_ID_MAP = dict((cmd.id, cmd) for cmd in [CMD_PING, CMD_PONG, CMD_FIND_NODE, CMD_NEIGHBOURS])


class DiscoveryProtocol(asyncio.DatagramProtocol):
    """A Kademlia-like protocol to discover RLPx nodes."""
    logger = get_extended_debug_logger("p2p.discovery.DiscoveryProtocol")
    transport: asyncio.DatagramTransport = None
    _max_neighbours_per_packet_cache = None

    def __init__(self,
                 privkey: datatypes.PrivateKey,
                 address: AddressAPI,
                 bootstrap_nodes: Sequence[NodeAPI],
                 cancel_token: CancelToken) -> None:
        self.privkey = privkey
        self.address = address
        self.bootstrap_nodes = bootstrap_nodes
        self.this_node = Node(self.pubkey, address)
        self.routing = RoutingTable(self.this_node)
        self.topic_table = TopicTable(self.logger)
        self.pong_callbacks = CallbackManager()
        self.ping_callbacks = CallbackManager()
        self.neighbours_callbacks = CallbackManager()
        self.topic_nodes_callbacks = CallbackManager()
        self.parity_pong_tokens: Dict[Hash32, Hash32] = {}
        self.cancel_token = CancelToken('DiscoveryProtocol').chain(cancel_token)

    def update_routing_table(self, node: NodeAPI) -> None:
        """Update the routing table entry for the given node."""
        eviction_candidate = self.routing.add_node(node)
        if eviction_candidate:
            # This means we couldn't add the node because its bucket is full, so schedule a bond()
            # with the least recently seen node on that bucket. If the bonding fails the node will
            # be removed from the bucket and a new one will be picked from the bucket's
            # replacement cache.
            asyncio.ensure_future(self.bond(eviction_candidate))

    async def bond(self, node: NodeAPI) -> bool:
        """Bond with the given node.

        Bonding consists of pinging the node, waiting for a pong and maybe a ping as well.
        It is necessary to do this at least once before we send find_node requests to a node.
        """
        if node in self.routing:
            return True
        elif node == self.this_node:
            return False

        token = self.send_ping_v4(node)
        log_version = "v4"

        try:
            got_pong = await self.wait_pong_v4(node, token)
        except AlreadyWaitingDiscoveryResponse:
            self.logger.debug("bonding failed, awaiting %s pong from %s", log_version, node)
            return False

        if not got_pong:
            self.logger.debug("bonding failed, didn't receive %s pong from %s", log_version, node)
            self.routing.remove_node(node)
            return False

        try:
            # Give the remote node a chance to ping us before we move on and
            # start sending find_node requests. It is ok for wait_ping() to
            # timeout and return false here as that just means the remote
            # remembers us.
            await self.wait_ping(node)
        except AlreadyWaitingDiscoveryResponse:
            self.logger.debug("binding failed, already waiting for ping")
            return False

        self.logger.debug2("bonding completed successfully with %s", node)
        self.update_routing_table(node)
        return True

    async def wait_ping(self, remote: NodeAPI) -> bool:
        """Wait for a ping from the given remote.

        This coroutine adds a callback to ping_callbacks and yields control until that callback is
        called or a timeout (k_request_timeout) occurs. At that point it returns whether or not
        a ping was received from the given node.
        """
        event = asyncio.Event()

        with self.ping_callbacks.acquire(remote, event.set):
            got_ping = False
            try:
                got_ping = await self.cancel_token.cancellable_wait(
                    event.wait(), timeout=constants.KADEMLIA_REQUEST_TIMEOUT)
                self.logger.debug2('got expected ping from %s', remote)
            except asyncio.TimeoutError:
                self.logger.debug2('timed out waiting for ping from %s', remote)

        return got_ping

    async def wait_pong_v4(self, remote: NodeAPI, token: Hash32) -> bool:
        event = asyncio.Event()
        callback = event.set
        return await self._wait_pong(remote, token, event, callback)

    async def _wait_pong(
            self, remote: NodeAPI, token: Hash32, event: asyncio.Event,
            callback: Callable[..., Any]) -> bool:
        """Wait for a pong from the given remote containing the given token.

        This coroutine adds a callback to pong_callbacks and yields control until the given event
        is set or a timeout (k_request_timeout) occurs. At that point it returns whether or not
        a pong was received with the given pingid.
        """
        pingid = self._mkpingid(token, remote)

        with self.pong_callbacks.acquire(pingid, callback):
            got_pong = False
            try:
                got_pong = await self.cancel_token.cancellable_wait(
                    event.wait(), timeout=constants.KADEMLIA_REQUEST_TIMEOUT)
                self.logger.debug2('got expected pong with token %s', encode_hex(token))
            except asyncio.TimeoutError:
                self.logger.debug2(
                    'timed out waiting for pong from %s (token == %s)',
                    remote,
                    encode_hex(token),
                )

        return got_pong

    async def wait_neighbours(self, remote: NodeAPI) -> Tuple[NodeAPI, ...]:
        """Wait for a neihgbours packet from the given node.

        Returns the list of neighbours received.
        """
        event = asyncio.Event()
        neighbours: List[NodeAPI] = []

        def process(response: List[NodeAPI]) -> None:
            neighbours.extend(response)
            # This callback is expected to be called multiple times because nodes usually
            # split the neighbours replies into multiple packets, so we only call event.set() once
            # we've received enough neighbours.
            if len(neighbours) >= constants.KADEMLIA_BUCKET_SIZE:
                event.set()

        with self.neighbours_callbacks.acquire(remote, process):
            try:
                await self.cancel_token.cancellable_wait(
                    event.wait(), timeout=constants.KADEMLIA_REQUEST_TIMEOUT)
                self.logger.debug2('got expected neighbours response from %s', remote)
            except asyncio.TimeoutError:
                self.logger.debug2(
                    'timed out waiting for %d neighbours from %s',
                    constants.KADEMLIA_BUCKET_SIZE,
                    remote,
                )

        return tuple(n for n in neighbours if n != self.this_node)

    def _mkpingid(self, token: Hash32, node: NodeAPI) -> Hash32:
        return Hash32(token + node.pubkey.to_bytes())

    def _send_find_node(self, node: NodeAPI, target_node_id: int) -> None:
        self.send_find_node_v4(node, target_node_id)

    async def lookup(self, node_id: int) -> Tuple[NodeAPI, ...]:
        """Lookup performs a network search for nodes close to the given target.

        It approaches the target by querying nodes that are closer to it on each iteration.  The
        given target does not need to be an actual node identifier.
        """
        nodes_asked: Set[NodeAPI] = set()
        nodes_seen: Set[NodeAPI] = set()

        async def _find_node(node_id: int, remote: NodeAPI) -> Tuple[NodeAPI, ...]:
            # Short-circuit in case our token has been triggered to avoid trying to send requests
            # over a transport that is probably closed already.
            self.cancel_token.raise_if_triggered()
            self._send_find_node(remote, node_id)
            candidates = await self.wait_neighbours(remote)
            if not candidates:
                self.logger.debug("got no candidates from %s, returning", remote)
                return tuple()
            all_candidates = tuple(c for c in candidates if c not in nodes_seen)
            candidates = tuple(
                c for c in all_candidates
                if (not self.ping_callbacks.locked(c) and not self.pong_callbacks.locked(c))
            )
            self.logger.debug2("got %s new candidates", len(candidates))
            # Add new candidates to nodes_seen so that we don't attempt to bond with failing ones
            # in the future.
            nodes_seen.update(candidates)
            bonded = await asyncio.gather(*(self.bond(c) for c in candidates))
            self.logger.debug2("bonded with %s candidates", bonded.count(True))
            return tuple(c for c in candidates if bonded[candidates.index(c)])

        def _exclude_if_asked(nodes: Iterable[NodeAPI]) -> List[NodeAPI]:
            nodes_to_ask = list(set(nodes).difference(nodes_asked))
            return sort_by_distance(nodes_to_ask, node_id)[:constants.KADEMLIA_FIND_CONCURRENCY]

        closest = self.routing.neighbours(node_id)
        self.logger.debug("starting lookup; initial neighbours: %s", closest)
        nodes_to_ask = _exclude_if_asked(closest)
        while nodes_to_ask:
            self.logger.debug2("node lookup; querying %s", nodes_to_ask)
            nodes_asked.update(nodes_to_ask)
            next_find_node_queries = (
                _find_node(node_id, n)
                for n
                in nodes_to_ask
                if not self.neighbours_callbacks.locked(n)
            )
            results = await asyncio.gather(*next_find_node_queries)
            for candidates in results:
                closest.extend(candidates)
            closest = sort_by_distance(closest, node_id)[:constants.KADEMLIA_BUCKET_SIZE]
            nodes_to_ask = _exclude_if_asked(closest)

        self.logger.debug(
            "lookup finished for target %s; closest neighbours: %s", to_hex(node_id), closest
        )
        return tuple(closest)

    async def lookup_random(self) -> Tuple[NodeAPI, ...]:
        return await self.lookup(random.randint(0, constants.KADEMLIA_MAX_NODE_ID))

    def get_random_bootnode(self) -> Iterator[NodeAPI]:
        if self.bootstrap_nodes:
            yield random.choice(self.bootstrap_nodes)
        else:
            self.logger.warning('No bootnodes available')

    def get_nodes_to_connect(self, count: int) -> Iterator[NodeAPI]:
        return self.routing.get_random_nodes(count)

    @property
    def pubkey(self) -> datatypes.PublicKey:
        return self.privkey.public_key

    def _get_handler(self, cmd: DiscoveryCommand) -> V4_HANDLER_TYPE:
        if cmd == CMD_PING:
            return self.recv_ping_v4
        elif cmd == CMD_PONG:
            return self.recv_pong_v4
        elif cmd == CMD_FIND_NODE:
            return self.recv_find_node_v4
        elif cmd == CMD_NEIGHBOURS:
            return self.recv_neighbours_v4
        else:
            raise ValueError(f"Unknown command: {cmd}")

    def _get_max_neighbours_per_packet(self) -> int:
        if self._max_neighbours_per_packet_cache is not None:
            return self._max_neighbours_per_packet_cache
        self._max_neighbours_per_packet_cache = _get_max_neighbours_per_packet()
        return self._max_neighbours_per_packet_cache

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        # we need to cast here because the signature in the base class dicates BaseTransport
        # and arguments can only be redefined contravariantly
        self.transport = cast(asyncio.DatagramTransport, transport)

    async def bootstrap(self) -> None:
        for node in self.bootstrap_nodes:
            uri = node.uri()
            pubkey, _, uri_tail = uri.partition('@')
            pubkey_head = pubkey[:16]
            pubkey_tail = pubkey[-8:]
            self.logger.debug("full-bootnode: %s", uri)
            self.logger.debug("bootnode: %s...%s@%s", pubkey_head, pubkey_tail, uri_tail)

        try:
            bonding_queries = (
                self.bond(n)
                for n
                in self.bootstrap_nodes
                if (not self.ping_callbacks.locked(n) and not self.pong_callbacks.locked(n))
            )
            bonded = await asyncio.gather(*bonding_queries)
            if not any(bonded):
                self.logger.info("Failed to bond with bootstrap nodes %s", self.bootstrap_nodes)
                return
            await self.lookup_random()
        except OperationCancelled as e:
            self.logger.info("Bootstrapping cancelled: %s", e)

    def datagram_received(self, data: Union[bytes, Text], addr: Tuple[str, int]) -> None:
        ip_address, udp_port = addr
        address = Address(ip_address, udp_port)
        self.receive(address, cast(bytes, data))

    def send(self, node: NodeAPI, message: bytes) -> None:
        self.transport.sendto(message, (node.address.ip, node.address.udp_port))

    async def stop(self) -> None:
        self.logger.info('stopping discovery')
        self.cancel_token.trigger()
        self.transport.close()
        # We run lots of asyncio tasks so this is to make sure they all get a chance to execute
        # and exit cleanly when they notice the cancel token has been triggered.
        await asyncio.sleep(0.1)

    def receive(self, address: AddressAPI, message: bytes) -> None:
        try:
            remote_pubkey, cmd_id, payload, message_hash = _unpack_v4(message)
        except DefectiveMessage as e:
            self.logger.error('error unpacking message (%s) from %s: %s', message, address, e)
            return

        # As of discovery version 4, expiration is the last element for all packets, so
        # we can validate that here, but if it changes we may have to do so on the
        # handler methods.
        expiration = rlp.sedes.big_endian_int.deserialize(payload[-1])
        if time.time() > expiration:
            self.logger.debug('received message already expired')
            return

        cmd = CMD_ID_MAP[cmd_id]
        if len(payload) != cmd.elem_count:
            self.logger.error('invalid %s payload: %s', cmd.name, payload)
            return
        node = Node(remote_pubkey, address)
        handler = self._get_handler(cmd)
        handler(node, payload, message_hash)

    def recv_pong_v4(self, node: NodeAPI, payload: Sequence[Any], _: Hash32) -> None:
        # The pong payload should have 3 elements: to, token, expiration
        _, token, _ = payload
        self.logger.debug2('<<< pong (v4) from %s (token == %s)', node, encode_hex(token))
        self.process_pong_v4(node, token)

    def recv_neighbours_v4(self, node: NodeAPI, payload: Sequence[Any], _: Hash32) -> None:
        # The neighbours payload should have 2 elements: nodes, expiration
        nodes, _ = payload
        neighbours = _extract_nodes_from_payload(node.address, nodes, self.logger)
        self.logger.debug2('<<< neighbours from %s: %s', node, neighbours)
        self.process_neighbours(node, neighbours)

    def recv_ping_v4(self, node: NodeAPI, _: Any, message_hash: Hash32) -> None:
        self.logger.debug2('<<< ping(v4) from %s', node)
        self.process_ping(node, message_hash)
        self.send_pong_v4(node, message_hash)

    def recv_find_node_v4(self, node: NodeAPI, payload: Sequence[Any], _: Hash32) -> None:
        # The find_node payload should have 2 elements: node_id, expiration
        self.logger.debug2('<<< find_node from %s', node)
        node_id, _ = payload
        if node not in self.routing:
            # FIXME: This is not correct; a node we've bonded before may have become unavailable
            # and thus removed from self.routing, but once it's back online we should accept
            # find_nodes from them.
            self.logger.debug('Ignoring find_node request from unknown node %s', node)
            return
        self.update_routing_table(node)
        found = self.routing.neighbours(big_endian_to_int(node_id))
        self.send_neighbours_v4(node, found)

    def send_ping_v4(self, node: NodeAPI) -> Hash32:
        version = rlp.sedes.big_endian_int.serialize(PROTO_VERSION)
        payload = (version, self.address.to_endpoint(), node.address.to_endpoint())
        message = _pack_v4(CMD_PING.id, payload, self.privkey)
        self.send(node, message)
        # Return the msg hash, which is used as a token to identify pongs.
        token = Hash32(message[:MAC_SIZE])
        self.logger.debug2('>>> ping (v4) %s (token == %s)', node, encode_hex(token))
        # XXX: This hack is needed because there are lots of parity 1.10 nodes out there that send
        # the wrong token on pong msgs (https://github.com/paritytech/parity/issues/8038). We
        # should get rid of this once there are no longer too many parity 1.10 nodes out there.
        parity_token = keccak(message[HEAD_SIZE + 1:])
        self.parity_pong_tokens[parity_token] = token
        return token

    def send_find_node_v4(self, node: NodeAPI, target_node_id: int) -> None:
        node_id = int_to_big_endian(
            target_node_id).rjust(constants.KADEMLIA_PUBLIC_KEY_SIZE // 8, b'\0')
        self.logger.debug2('>>> find_node to %s', node)
        message = _pack_v4(CMD_FIND_NODE.id, tuple([node_id]), self.privkey)
        self.send(node, message)

    def send_pong_v4(self, node: NodeAPI, token: Hash32) -> None:
        self.logger.debug2('>>> pong %s', node)
        payload = (node.address.to_endpoint(), token)
        message = _pack_v4(CMD_PONG.id, payload, self.privkey)
        self.send(node, message)

    def send_neighbours_v4(self, node: NodeAPI, neighbours: List[NodeAPI]) -> None:
        nodes = []
        neighbours = sorted(neighbours)
        for n in neighbours:
            nodes.append(n.address.to_endpoint() + [n.pubkey.to_bytes()])

        max_neighbours = self._get_max_neighbours_per_packet()
        for i in range(0, len(nodes), max_neighbours):
            message = _pack_v4(
                CMD_NEIGHBOURS.id, tuple([nodes[i:i + max_neighbours]]), self.privkey)
            self.logger.debug2('>>> neighbours to %s: %s',
                               node, neighbours[i:i + max_neighbours])
            self.send(node, message)

    def process_neighbours(self, remote: NodeAPI, neighbours: List[NodeAPI]) -> None:
        """Process a neighbours response.

        Neighbours responses should only be received as a reply to a find_node, and that is only
        done as part of node lookup, so the actual processing is left to the callback from
        neighbours_callbacks, which is added (and removed after it's done or timed out) in
        wait_neighbours().
        """
        try:
            callback = self.neighbours_callbacks.get_callback(remote)
        except KeyError:
            self.logger.debug(
                'unexpected neighbours from %s, probably came too late', remote)
        else:
            callback(neighbours)

    def process_pong_v4(self, remote: NodeAPI, token: Hash32) -> None:
        """Process a pong packet.

        Pong packets should only be received as a response to a ping, so the actual processing is
        left to the callback from pong_callbacks, which is added (and removed after it's done
        or timed out) in wait_pong().
        """
        # XXX: This hack is needed because there are lots of parity 1.10 nodes out there that send
        # the wrong token on pong msgs (https://github.com/paritytech/parity/issues/8038). We
        # should get rid of this once there are no longer too many parity 1.10 nodes out there.
        if token in self.parity_pong_tokens:
            # This is a pong from a buggy parity node, so need to lookup the actual token we're
            # expecting.
            token = self.parity_pong_tokens.pop(token)
        else:
            # This is a pong from a non-buggy node, so just cleanup self.parity_pong_tokens.
            self.parity_pong_tokens = eth_utils.toolz.valfilter(
                lambda val: val != token, self.parity_pong_tokens)

        pingid = self._mkpingid(token, remote)

        try:
            callback = self.pong_callbacks.get_callback(pingid)
        except KeyError:
            self.logger.debug('unexpected v4 pong from %s (token == %s)', remote, encode_hex(token))
        else:
            callback()

    def process_ping(self, remote: NodeAPI, hash_: Hash32) -> None:
        """Process a received ping packet.

        A ping packet may come any time, unrequested, or may be prompted by us bond()ing with a
        new node. In the former case we'll just update the sender's entry in our routing table and
        reply with a pong, whereas in the latter we'll also fire a callback from ping_callbacks.
        """
        if remote == self.this_node:
            self.logger.info('Invariant: received ping from this_node: %s', remote)
            return
        else:
            self.update_routing_table(remote)
        # Sometimes a ping will be sent to us as part of the bonding
        # performed the first time we see a node, and it is in those cases that
        # a callback will exist.
        try:
            callback = self.ping_callbacks.get_callback(remote)
        except KeyError:
            pass
        else:
            callback()


class PreferredNodeDiscoveryProtocol(DiscoveryProtocol):
    """
    A DiscoveryProtocol which has a list of preferred nodes which it will prioritize using before
    trying to find nodes.  Each preferred node can only be used once every
    preferred_node_recycle_time seconds.
    """
    preferred_nodes: Sequence[NodeAPI] = None
    preferred_node_recycle_time: int = 300
    _preferred_node_tracker: Dict[NodeAPI, float] = None

    def __init__(self,
                 privkey: datatypes.PrivateKey,
                 address: AddressAPI,
                 bootstrap_nodes: Sequence[NodeAPI],
                 preferred_nodes: Sequence[NodeAPI],
                 cancel_token: CancelToken) -> None:
        super().__init__(privkey, address, bootstrap_nodes, cancel_token)

        self.preferred_nodes = preferred_nodes
        self.logger.info('Preferred peers: %s', self.preferred_nodes)
        self._preferred_node_tracker = collections.defaultdict(lambda: 0)

    @to_tuple
    def _get_eligible_preferred_nodes(self) -> Iterator[NodeAPI]:
        """
        Return nodes from the preferred_nodes which have not been used within
        the last preferred_node_recycle_time
        """
        for node in self.preferred_nodes:
            last_used = self._preferred_node_tracker[node]
            if time.time() - last_used > self.preferred_node_recycle_time:
                yield node

    def _get_random_preferred_node(self) -> NodeAPI:
        """
        Return a random node from the preferred list.
        """
        eligible_nodes = self._get_eligible_preferred_nodes()
        if not eligible_nodes:
            raise NoEligibleNodes("No eligible preferred nodes available")
        node = random.choice(eligible_nodes)
        return node

    def get_random_bootnode(self) -> Iterator[NodeAPI]:
        """
        Return a single node to bootstrap, preferring nodes from the preferred list.
        """
        try:
            node = self._get_random_preferred_node()
            self._preferred_node_tracker[node] = time.time()
            yield node
        except NoEligibleNodes:
            yield from super().get_random_bootnode()

    def get_nodes_to_connect(self, count: int) -> Iterator[NodeAPI]:
        """
        Return up to `count` nodes, preferring nodes from the preferred list.
        """
        preferred_nodes = self._get_eligible_preferred_nodes()[:count]
        for node in preferred_nodes:
            self._preferred_node_tracker[node] = time.time()
            yield node

        num_nodes_needed = max(0, count - len(preferred_nodes))
        yield from super().get_nodes_to_connect(num_nodes_needed)


class StaticDiscoveryService(BaseService):
    """A 'discovery' service that only connects to the given nodes"""
    _static_peers: Tuple[NodeAPI, ...]
    _event_bus: EndpointAPI

    def __init__(
            self,
            event_bus: EndpointAPI,
            static_peers: Sequence[NodeAPI],
            token: CancelToken = None) -> None:
        super().__init__(token)
        self._event_bus = event_bus
        self._static_peers = tuple(static_peers)

    async def handle_get_peer_candidates_requests(self) -> None:
        async for event in self._event_bus.stream(PeerCandidatesRequest):
            candidates = self._select_nodes(event.max_candidates)
            await self._broadcast_nodes(event, candidates)

    async def handle_get_random_bootnode_requests(self) -> None:
        async for event in self._event_bus.stream(RandomBootnodeRequest):
            candidates = self._select_nodes(1)
            await self._broadcast_nodes(event, candidates)

    def _select_nodes(self, max_nodes: int) -> Tuple[NodeAPI, ...]:
        if max_nodes >= len(self._static_peers):
            candidates = self._static_peers
            self.logger.debug2("Replying with all static nodes: %r", candidates)
        else:
            candidates = tuple(random.sample(self._static_peers, max_nodes))
            self.logger.debug2("Replying with subset of static nodes: %r", candidates)
        return candidates

    async def _broadcast_nodes(
            self,
            event: BaseRequestResponseEvent[PeerCandidatesResponse],
            nodes: Sequence[NodeAPI]) -> None:
        await self._event_bus.broadcast(
            event.expected_response_type()(tuple(nodes)),
            event.broadcast_config()
        )

    async def _run(self) -> None:
        self.run_daemon_task(self.handle_get_peer_candidates_requests())
        self.run_daemon_task(self.handle_get_random_bootnode_requests())

        await self.cancel_token.wait()


class NoopDiscoveryService(BaseService):
    'A stub "discovery service" which does nothing'

    def __init__(self, event_bus: EndpointAPI, token: CancelToken = None) -> None:
        super().__init__(token)
        self._event_bus = event_bus

    async def handle_get_peer_candidates_requests(self) -> None:
        async for event in self._event_bus.stream(PeerCandidatesRequest):
            self.logger.debug("Servicing request for more peer candidates")

            await self._event_bus.broadcast(
                event.expected_response_type()(tuple()),
                event.broadcast_config()
            )

    async def handle_get_random_bootnode_requests(self) -> None:
        async for event in self._event_bus.stream(RandomBootnodeRequest):
            self.logger.debug("Servicing request for boot nodes")

            await self._event_bus.broadcast(
                event.expected_response_type()(tuple()),
                event.broadcast_config()
            )

    async def _run(self) -> None:
        self.run_daemon_task(self.handle_get_peer_candidates_requests())
        self.run_daemon_task(self.handle_get_random_bootnode_requests())

        await self.cancel_token.wait()


class DiscoveryService(BaseService):
    _last_lookup: float = 0
    _lookup_interval: int = 30

    def __init__(self,
                 proto: DiscoveryProtocol,
                 port: int,
                 event_bus: EndpointAPI,
                 token: CancelToken = None) -> None:
        super().__init__(token)
        self.proto = proto
        self.port = port
        self._event_bus = event_bus
        self._lookup_running = asyncio.Lock()

    async def handle_get_peer_candidates_requests(self) -> None:
        async for event in self.wait_iter(self._event_bus.stream(PeerCandidatesRequest)):

            self.run_task(self.maybe_lookup_random_node())

            nodes = tuple(self.proto.get_nodes_to_connect(event.max_candidates))

            self.logger.debug2("Broadcasting peer candidates (%s)", nodes)
            await self._event_bus.broadcast(
                event.expected_response_type()(nodes),
                event.broadcast_config()
            )

    async def handle_get_random_bootnode_requests(self) -> None:
        async for event in self.wait_iter(self._event_bus.stream(RandomBootnodeRequest)):

            nodes = tuple(self.proto.get_random_bootnode())

            self.logger.debug2("Broadcasting random boot nodes (%s)", nodes)
            await self._event_bus.broadcast(
                event.expected_response_type()(nodes),
                event.broadcast_config()
            )

    async def _run(self) -> None:
        self.run_daemon_task(self.handle_get_peer_candidates_requests())
        self.run_daemon_task(self.handle_get_random_bootnode_requests())

        await self._start_udp_listener()
        self.run_task(self.proto.bootstrap())
        await self.cancel_token.wait()

    async def _start_udp_listener(self) -> None:
        loop = asyncio.get_event_loop()
        # TODO: Support IPv6 addresses as well.
        await loop.create_datagram_endpoint(
            lambda: self.proto,
            local_addr=('0.0.0.0', self.port),
            family=socket.AF_INET)

    async def maybe_lookup_random_node(self) -> None:
        if self._last_lookup + self._lookup_interval > time.time():
            return
        elif self._lookup_running.locked():
            self.logger.debug("Node discovery lookup already in progress, not running another")
            return
        async with self._lookup_running:
            # This method runs in the background, so we must catch OperationCancelled here
            # otherwise asyncio will warn that its exception was never retrieved.
            try:
                await self.proto.lookup_random()
            except OperationCancelled:
                pass
            finally:
                self._last_lookup = time.time()

    async def _cleanup(self) -> None:
        await self.proto.stop()


class NodeTicketInfo:
    # The serial number of the last ticket we issued for a given remote node. New tickets are
    # issued when a node sends a PING msg containing one or more topics.
    last_issued: int = 0
    # The serial number of the last ticket used by a given remote node. Tickets are marked as used
    # when a node sends a REGISTER_TICKET msg using a ticket previously issued.
    last_used: int = 0


class TopicTable:
    registration_lifetime = 60 * 60
    topics: DefaultDict[bytes, 'collections.OrderedDict[NodeAPI, float]']

    def __init__(self, logger: ExtendedDebugLogger) -> None:
        self.logger = logger
        # A per-topic FIFO set of nodes.
        self.topics = collections.defaultdict(collections.OrderedDict)
        # The IDs of the last issued/used tickets for any given node.
        self.node_tickets: Dict[NodeAPI, NodeTicketInfo] = {}

    def add_node(self, node: NodeAPI, topic: bytes) -> None:
        entries = self.topics[topic]
        if node in entries:
            entries.pop(node)
        while len(entries) >= MAX_ENTRIES_PER_TOPIC:
            entries.popitem(last=False)
        entries[node] = time.time() + self.registration_lifetime

    def get_nodes(self, topic: bytes) -> Tuple[NodeAPI, ...]:
        if topic not in self.topics:
            return tuple()
        else:
            now = time.time()
            entries = [(node, expiry) for node, expiry in self.topics[topic].items()
                       if expiry > now]
            self.topics[topic] = collections.OrderedDict(entries)
            return tuple(node for node, _ in entries)

    def use_ticket(self, node: NodeAPI, ticket_serial: int, topic: bytes) -> None:
        ticket_info = self.node_tickets.get(node)
        if ticket_info is None:
            self.logger.debug("No ticket found for %s", node)
            return

        if ticket_serial != ticket_info.last_issued:
            self.logger.debug("Wrong ticket for %s, expected %d, got %d", node,
                              ticket_info.last_issued, ticket_serial)
            return

        ticket_info.last_used = ticket_serial
        self.add_node(node, topic)

    def issue_ticket(self, node: NodeAPI) -> int:
        node_info = self.node_tickets.setdefault(node, NodeTicketInfo())
        node_info.last_issued += 1
        return node_info.last_issued


class Ticket:

    def __init__(self, node: NodeAPI, pong: bytes, topics: List[bytes],
                 wait_periods: List[float]) -> None:
        now = time.time()
        self.issue_time = now
        self.node = node
        self.pong = pong
        self.topics = topics
        self.registration_times = [now + wait_period for wait_period in wait_periods]

    def __repr__(self) -> str:
        return f"Ticket({self.node}:{self.topics})"


@to_list
def _extract_nodes_from_payload(
        sender: AddressAPI,
        payload: List[Tuple[str, bytes, bytes, bytes]],
        logger: ExtendedDebugLogger) -> Iterator[NodeAPI]:
    for item in payload:
        ip, udp_port, tcp_port, node_id = item
        address = Address.from_endpoint(ip, udp_port, tcp_port)
        if check_relayed_addr(sender, address):
            yield Node(keys.PublicKey(node_id), address)
        else:
            logger.debug("Skipping invalid address %s relayed by %s", address, sender)


def _get_max_neighbours_per_packet() -> int:
    # As defined in https://github.com/ethereum/devp2p/blob/master/rlpx.md, the max size of a
    # datagram must be 1280 bytes, so when sending neighbours packets we must include up to
    # _max_neighbours_per_packet and if there's more than that split them across multiple
    # packets.
    # Use an IPv6 address here as we're interested in the size of the biggest possible node
    # representation.
    addr = Address('::1', 30303, 30303)
    node_data = addr.to_endpoint() + [b'\x00' * (constants.KADEMLIA_PUBLIC_KEY_SIZE // 8)]
    neighbours = [node_data]
    expiration = rlp.sedes.big_endian_int.serialize(_get_msg_expiration())
    payload = rlp.encode([neighbours] + [expiration])
    while HEAD_SIZE + len(payload) <= 1280:
        neighbours.append(node_data)
        payload = rlp.encode([neighbours] + [expiration])
    return len(neighbours) - 1


def _pack_v4(cmd_id: int, payload: Sequence[Any], privkey: datatypes.PrivateKey) -> bytes:
    """Create and sign a UDP message to be sent to a remote node.

    See https://github.com/ethereum/devp2p/blob/master/rlpx.md#node-discovery for information on
    how UDP packets are structured.
    """
    cmd_id = to_bytes(cmd_id)
    expiration = rlp.sedes.big_endian_int.serialize(_get_msg_expiration())
    encoded_data = cmd_id + rlp.encode(tuple(payload) + (expiration,))
    signature = privkey.sign_msg(encoded_data)
    message_hash = keccak(signature.to_bytes() + encoded_data)
    return message_hash + signature.to_bytes() + encoded_data


def _unpack_v4(message: bytes) -> Tuple[datatypes.PublicKey, int, Tuple[Any, ...], Hash32]:
    """Unpack a discovery v4 UDP message received from a remote node.

    Returns the public key used to sign the message, the cmd ID, payload and hash.
    """
    message_hash = Hash32(message[:MAC_SIZE])
    if message_hash != keccak(message[MAC_SIZE:]):
        raise WrongMAC("Wrong msg mac")
    signature = keys.Signature(message[MAC_SIZE:HEAD_SIZE])
    signed_data = message[HEAD_SIZE:]
    remote_pubkey = signature.recover_public_key_from_msg(signed_data)
    cmd_id = message[HEAD_SIZE]
    try:
        cmd = CMD_ID_MAP[cmd_id]
    except KeyError as e:
        raise UnknownCommand(f"Invalid Command ID {cmd_id}") from e
    payload = tuple(rlp.decode(message[HEAD_SIZE + 1:], strict=False))
    # Ignore excessive list elements as required by EIP-8.
    payload = payload[:cmd.elem_count]
    return remote_pubkey, cmd_id, payload, message_hash


def _get_msg_expiration() -> int:
    return int(time.time() + EXPIRATION)


class CallbackLock:
    def __init__(self,
                 callback: Callable[..., Any],
                 timeout: float = 2 * constants.KADEMLIA_REQUEST_TIMEOUT) -> None:
        self.callback = callback
        self.timeout = timeout
        self.created_at = time.time()

    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.timeout


class CallbackManager(UserDict):
    @contextlib.contextmanager
    def acquire(self,
                key: Hashable,
                callback: Callable[..., Any]) -> Iterator[CallbackLock]:
        if key in self:
            if not self.locked(key):
                del self[key]
            else:
                raise AlreadyWaitingDiscoveryResponse(f"Already waiting on callback for: {key}")

        lock = CallbackLock(callback)
        self[key] = lock

        try:
            yield lock
        finally:
            del self[key]

    def get_callback(self, key: Hashable) -> Callable[..., Any]:
        return self[key].callback

    def locked(self, key: Hashable) -> bool:
        try:
            lock = self[key]
        except KeyError:
            return False
        else:
            if lock.is_expired:
                return False
            else:
                return True
