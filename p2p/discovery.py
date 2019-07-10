"""
The Node Discovery protocol provides a way to find RLPx nodes that can be connected to. It uses a
Kademlia-like protocol to maintain a distributed database of the IDs and endpoints of all
listening nodes.

More information at https://github.com/ethereum/devp2p/blob/master/rlpx.md#node-discovery
"""
import asyncio
import collections
import contextlib
import logging
import random
import socket
import time
from typing import (
    Any,
    Callable,
    cast,
    Dict,
    Hashable,
    Iterable,
    Iterator,
    List,
    Sequence,
    Set,
    Text,
    Tuple,
    Type,
    TYPE_CHECKING,
    Union,
)

import eth_utils.toolz

from lahja import (
    AsyncioEndpoint,
)

import rlp

from eth_typing import Hash32

from eth_utils import (
    encode_hex,
    remove_0x_prefix,
    text_if_str,
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

from eth.tools.logging import ExtendedDebugLogger, DEBUG2_LEVEL_NUM

from cancel_token import CancelToken, OperationCancelled

from p2p.events import (
    PeerCandidatesRequest,
    RandomBootnodeRequest,
    BaseRequestResponseEvent,
    PeerCandidatesResponse,
)
from p2p.exceptions import AlreadyWaitingDiscoveryResponse, NoEligibleNodes, UnableToGetDiscV5Ticket
from p2p.kademlia import Node as KademliaNode
from p2p import kademlia
from p2p import protocol
from p2p.service import BaseService

if TYPE_CHECKING:
    # Promoted workaround for inheriting from generic stdlib class
    # https://github.com/python/mypy/issues/5264#issuecomment-399407428
    UserDict = collections.UserDict[Hashable, 'CallbackLock']
else:
    UserDict = collections.UserDict

# V4 handler methods take a Node, payload and msg_hash as arguments.
V4_HANDLER_TYPE = Callable[[kademlia.Node, Tuple[Any, ...], Hash32], None]
# V5 handler methods take a Node, payload, msg_hash and msg as arguments.
V5_HANDLER_TYPE = Callable[[kademlia.Node, Tuple[Any, ...], Hash32, bytes], None]

MAX_ENTRIES_PER_TOPIC = 50
# UDP packet constants.
V5_ID_STRING = b"temporary discovery v5"
MAC_SIZE = 256 // 8  # 32
SIG_SIZE = 520 // 8  # 65
HEAD_SIZE = MAC_SIZE + SIG_SIZE  # 97
HEAD_SIZE_V5 = len(V5_ID_STRING) + SIG_SIZE  # 87
EXPIRATION = 60  # let messages expire after N secondes
PROTO_VERSION = 4
PROTO_VERSION_V5 = 5


class DefectiveMessage(Exception):
    pass


class WrongMAC(DefectiveMessage):
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

CMD_PING_V5 = DiscoveryCommand("ping", 1, 5)
CMD_PONG_V5 = DiscoveryCommand("pong", 2, 6)
CMD_FIND_NODEHASH = DiscoveryCommand("find_nodehash", 5, 2)
CMD_TOPIC_REGISTER = DiscoveryCommand("topic_register", 6, 3)
CMD_TOPIC_QUERY = DiscoveryCommand("topic_query", 7, 2)
CMD_TOPIC_NODES = DiscoveryCommand("topic_nodes", 8, 2)
CMD_ID_MAP_V5 = dict(
    (cmd.id, cmd)
    for cmd in [
        CMD_PING_V5,
        CMD_PONG_V5,
        CMD_FIND_NODE,
        CMD_NEIGHBOURS,
        CMD_FIND_NODEHASH,
        CMD_TOPIC_REGISTER,
        CMD_TOPIC_QUERY,
        CMD_TOPIC_NODES])


class DiscoveryProtocol(asyncio.DatagramProtocol):
    """A Kademlia-like protocol to discover RLPx nodes."""
    logger: ExtendedDebugLogger = cast(ExtendedDebugLogger,
                                       logging.getLogger("p2p.discovery.DiscoveryProtocol"))
    transport: asyncio.DatagramTransport = None
    use_v5 = False
    _max_neighbours_per_packet_cache = None

    def __init__(self,
                 privkey: datatypes.PrivateKey,
                 address: kademlia.Address,
                 bootstrap_nodes: Tuple[kademlia.Node, ...],
                 cancel_token: CancelToken) -> None:
        self.privkey = privkey
        self.address = address
        self.bootstrap_nodes = bootstrap_nodes
        self.this_node = kademlia.Node(self.pubkey, address)
        self.routing = kademlia.RoutingTable(self.this_node)
        self.topic_table = TopicTable(self.logger)
        self.pong_callbacks = CallbackManager()
        self.ping_callbacks = CallbackManager()
        self.neighbours_callbacks = CallbackManager()
        self.topic_nodes_callbacks = CallbackManager()
        self.parity_pong_tokens: Dict[Hash32, Hash32] = {}
        self.cancel_token = CancelToken('DiscoveryProtocol').chain(cancel_token)

    def update_routing_table(self, node: kademlia.Node) -> None:
        """Update the routing table entry for the given node."""
        eviction_candidate = self.routing.add_node(node)
        if eviction_candidate:
            # This means we couldn't add the node because its bucket is full, so schedule a bond()
            # with the least recently seen node on that bucket. If the bonding fails the node will
            # be removed from the bucket and a new one will be picked from the bucket's
            # replacement cache.
            asyncio.ensure_future(self.bond(eviction_candidate))

    async def bond(self, node: kademlia.Node) -> bool:
        """Bond with the given node.

        Bonding consists of pinging the node, waiting for a pong and maybe a ping as well.
        It is necessary to do this at least once before we send find_node requests to a node.
        """
        if node in self.routing:
            return True
        elif node == self.this_node:
            return False

        if self.use_v5:
            token = self.send_ping_v5(node, [])
            log_version = "v5"
        else:
            token = self.send_ping_v4(node)
            log_version = "v4"

        try:
            if self.use_v5:
                got_pong, _, _ = await self.wait_pong_v5(node, token)
            else:
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

    async def wait_ping(self, remote: kademlia.Node) -> bool:
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
                    event.wait(), timeout=kademlia.k_request_timeout)
                self.logger.debug2('got expected ping from %s', remote)
            except TimeoutError:
                self.logger.debug2('timed out waiting for ping from %s', remote)

        return got_ping

    async def wait_pong_v4(self, remote: kademlia.Node, token: Hash32) -> bool:
        event = asyncio.Event()
        callback = event.set
        return await self._wait_pong(remote, token, event, callback)

    async def _wait_pong(
            self, remote: kademlia.Node, token: Hash32, event: asyncio.Event,
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
                    event.wait(), timeout=kademlia.k_request_timeout)
                self.logger.debug2('got expected pong with token %s', encode_hex(token))
            except TimeoutError:
                self.logger.debug2(
                    'timed out waiting for pong from %s (token == %s)',
                    remote,
                    encode_hex(token),
                )

        return got_pong

    async def wait_neighbours(self, remote: kademlia.Node) -> Tuple[kademlia.Node, ...]:
        """Wait for a neihgbours packet from the given node.

        Returns the list of neighbours received.
        """
        event = asyncio.Event()
        neighbours: List[kademlia.Node] = []

        def process(response: List[kademlia.Node]) -> None:
            neighbours.extend(response)
            # This callback is expected to be called multiple times because nodes usually
            # split the neighbours replies into multiple packets, so we only call event.set() once
            # we've received enough neighbours.
            if len(neighbours) >= kademlia.k_bucket_size:
                event.set()

        with self.neighbours_callbacks.acquire(remote, process):
            try:
                await self.cancel_token.cancellable_wait(
                    event.wait(), timeout=kademlia.k_request_timeout)
                self.logger.debug2('got expected neighbours response from %s', remote)
            except TimeoutError:
                self.logger.debug2(
                    'timed out waiting for %d neighbours from %s', kademlia.k_bucket_size, remote)

        return tuple(n for n in neighbours if n != self.this_node)

    def _mkpingid(self, token: Hash32, node: kademlia.Node) -> Hash32:
        return Hash32(token + node.pubkey.to_bytes())

    def _send_find_node(self, node: kademlia.Node, target_node_id: int) -> None:
        if self.use_v5:
            self.send_find_node_v5(node, target_node_id)
        else:
            self.send_find_node_v4(node, target_node_id)

    async def lookup(self, node_id: int) -> Tuple[kademlia.Node, ...]:
        """Lookup performs a network search for nodes close to the given target.

        It approaches the target by querying nodes that are closer to it on each iteration.  The
        given target does not need to be an actual node identifier.
        """
        nodes_asked: Set[kademlia.Node] = set()
        nodes_seen: Set[kademlia.Node] = set()

        async def _find_node(node_id: int, remote: kademlia.Node) -> Tuple[kademlia.Node, ...]:
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

        def _exclude_if_asked(nodes: Iterable[kademlia.Node]) -> List[kademlia.Node]:
            nodes_to_ask = list(set(nodes).difference(nodes_asked))
            return kademlia.sort_by_distance(nodes_to_ask, node_id)[:kademlia.k_find_concurrency]

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
            closest = kademlia.sort_by_distance(closest, node_id)[:kademlia.k_bucket_size]
            nodes_to_ask = _exclude_if_asked(closest)

        self.logger.debug(
            "lookup finished for target %s; closest neighbours: %s", to_hex(node_id), closest
        )
        return tuple(closest)

    async def lookup_random(self) -> Tuple[kademlia.Node, ...]:
        return await self.lookup(random.randint(0, kademlia.k_max_node_id))

    def get_random_bootnode(self) -> Iterator[kademlia.Node]:
        if self.bootstrap_nodes:
            yield random.choice(self.bootstrap_nodes)
        else:
            self.logger.warning('No bootnodes available')

    def get_nodes_to_connect(self, count: int) -> Iterator[kademlia.Node]:
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
            self.logger.info("bootnode: %s...%s@%s", pubkey_head, pubkey_tail, uri_tail)

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
        address = kademlia.Address(ip_address, udp_port)
        # The prefix below is what geth uses to identify discv5 msgs.
        # https://github.com/ethereum/go-ethereum/blob/c4712bf96bc1bae4a5ad4600e9719e4a74bde7d5/p2p/discv5/udp.go#L149  # noqa: E501
        if text_if_str(to_bytes, data).startswith(V5_ID_STRING):
            self.receive_v5(address, cast(bytes, data))
        else:
            self.receive(address, cast(bytes, data))

    def send(self, node: kademlia.Node, message: bytes) -> None:
        self.transport.sendto(message, (node.address.ip, node.address.udp_port))

    async def stop(self) -> None:
        self.logger.info('stopping discovery')
        self.cancel_token.trigger()
        self.transport.close()
        # We run lots of asyncio tasks so this is to make sure they all get a chance to execute
        # and exit cleanly when they notice the cancel token has been triggered.
        await asyncio.sleep(0.1)

    def receive(self, address: kademlia.Address, message: bytes) -> None:
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
        node = kademlia.Node(remote_pubkey, address)
        handler = self._get_handler(cmd)
        handler(node, payload, message_hash)

    def recv_pong_v4(self, node: kademlia.Node, payload: Tuple[Any, ...], _: Hash32) -> None:
        # The pong payload should have 3 elements: to, token, expiration
        _, token, _ = payload
        self.logger.debug2('<<< pong (v4) from %s (token == %s)', node, encode_hex(token))
        self.process_pong_v4(node, token)

    def recv_neighbours_v4(self, node: kademlia.Node, payload: Tuple[Any, ...], _: Hash32) -> None:
        # The neighbours payload should have 2 elements: nodes, expiration
        nodes, _ = payload
        neighbours = _extract_nodes_from_payload(node.address, nodes, self.logger)
        self.logger.debug2('<<< neighbours from %s: %s', node, neighbours)
        self.process_neighbours(node, neighbours)

    def recv_ping_v4(self, node: kademlia.Node, _: Any, message_hash: Hash32) -> None:
        self.logger.debug2('<<< ping(v4) from %s', node)
        self.process_ping(node, message_hash)
        self.send_pong_v4(node, message_hash)

    def recv_find_node_v4(self, node: kademlia.Node, payload: Tuple[Any, ...], _: Hash32) -> None:
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

    def send_ping_v4(self, node: kademlia.Node) -> Hash32:
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

    def send_find_node_v4(self, node: kademlia.Node, target_node_id: int) -> None:
        node_id = int_to_big_endian(
            target_node_id).rjust(kademlia.k_pubkey_size // 8, b'\0')
        self.logger.debug2('>>> find_node to %s', node)
        message = _pack_v4(CMD_FIND_NODE.id, tuple([node_id]), self.privkey)
        self.send(node, message)

    def send_pong_v4(self, node: kademlia.Node, token: Hash32) -> None:
        self.logger.debug2('>>> pong %s', node)
        payload = (node.address.to_endpoint(), token)
        message = _pack_v4(CMD_PONG.id, payload, self.privkey)
        self.send(node, message)

    def send_neighbours_v4(self, node: kademlia.Node, neighbours: List[kademlia.Node]) -> None:
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

    def process_neighbours(self, remote: kademlia.Node, neighbours: List[kademlia.Node]) -> None:
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

    def process_pong_v4(self, remote: kademlia.Node, token: Hash32) -> None:
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

    def process_ping(self, remote: kademlia.Node, hash_: Hash32) -> None:
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

    #
    # Discovery v5 specific methods
    #

    def send_v5(self, node: kademlia.Node, message: bytes) -> Hash32:
        msg_hash = keccak(message)
        self.send(node, V5_ID_STRING + message)
        return msg_hash

    def _get_handler_v5(self, cmd: DiscoveryCommand) -> V5_HANDLER_TYPE:
        if cmd == CMD_PING_V5:
            return self.recv_ping_v5
        elif cmd == CMD_PONG_V5:
            return self.recv_pong_v5
        elif cmd == CMD_FIND_NODE:
            return self.recv_find_node_v5
        elif cmd == CMD_NEIGHBOURS:
            return self.recv_neighbours_v5
        elif cmd == CMD_FIND_NODEHASH:
            return self.recv_find_nodehash
        elif cmd == CMD_TOPIC_REGISTER:
            return self.recv_topic_register
        elif cmd == CMD_TOPIC_QUERY:
            return self.recv_topic_query
        elif cmd == CMD_TOPIC_NODES:
            return self.recv_topic_nodes
        else:
            raise ValueError(f"Unknown command: {cmd}")

    def receive_v5(self, address: kademlia.Address, message: bytes) -> None:
        try:
            remote_pubkey, cmd_id, payload, message_hash = _unpack_v5(message)
        except DefectiveMessage as e:
            self.logger.error('error unpacking message (%s) from %s: %s', message, address, e)
            return

        cmd = CMD_ID_MAP_V5[cmd_id]
        if len(payload) != cmd.elem_count:
            self.logger.error('invalid %s payload: %s', cmd.name, payload)
            return
        node = kademlia.Node(remote_pubkey, address)
        handler = self._get_handler_v5(cmd)
        handler(node, payload, message_hash, message)

    def recv_ping_v5(self, node: kademlia.Node, payload: Tuple[Any, ...],
                     message_hash: Hash32, _: bytes) -> None:
        # version, from, to, expiration, topics
        _, _, _, _, topics = payload
        self.logger.debug2('<<< ping(v5) from %s, topics: %s', node, topics)
        self.process_ping(node, message_hash)
        topic_hash = keccak(rlp.encode(topics))
        ticket_serial = self.topic_table.issue_ticket(node)
        # TODO: Generate wait_periods list according to spec.
        wait_periods: List[int] = [60] * len(topics)
        self.send_pong_v5(node, message_hash, topic_hash, ticket_serial, wait_periods)

    def recv_pong_v5(
            self, node: kademlia.Node, payload: Tuple[Any, ...], _: Hash32, raw_msg: bytes) -> None:
        # to, token, expiration, topic_hash, ticket_serial, wait_periods
        _, token, _, _, _, wait_periods = payload
        wait_periods = [big_endian_to_int(wait_period) for wait_period in wait_periods]
        self.logger.debug2('<<< pong (v5) from %s (token == %s)', node, encode_hex(token))
        self.process_pong_v5(node, token, raw_msg, wait_periods)

    def recv_find_node_v5(self, node: kademlia.Node, payload: Tuple[Any, ...],
                          msg_hash: Hash32, _: bytes) -> None:
        # FIND_NODE in v5 is identical to v4, so just call the v4 handler.
        self.recv_find_node_v4(node, payload, msg_hash)

    def recv_neighbours_v5(self, node: kademlia.Node, payload: Tuple[Any, ...],
                           msg_hash: Hash32, _: bytes) -> None:
        # NEIGHBOURS in v5 is identical to v4, so just call the v4 handler.
        self.recv_neighbours_v4(node, payload, msg_hash)

    def recv_find_nodehash(self, node: kademlia.Node, payload: Tuple[Any, ...],
                           _: Hash32, _b: bytes) -> None:
        target_hash, _ = payload
        self.logger.debug2('<<< find_nodehash from %s, target: %s', node, target_hash)
        # TODO: Reply with a neighbours msg.

    def recv_topic_register(self, node: kademlia.Node, payload: Tuple[Any, ...],
                            _: Hash32, _m: bytes) -> None:
        topics, idx, raw_pong = payload
        topic_idx = big_endian_to_int(idx)
        self.logger.debug2(
            '<<< topic_register from %s, topics: %s, idx: %d', node, topics, topic_idx)
        key, cmd_id, pong_payload, _ = _unpack_v5(raw_pong)
        _, _, _, _, ticket_serial, _ = pong_payload
        self.topic_table.use_ticket(node, big_endian_to_int(ticket_serial), topics[topic_idx])

    def recv_topic_query(self, node: kademlia.Node, payload: Tuple[Any, ...],
                         message_hash: Hash32, _: bytes) -> None:
        topic, _ = payload
        self.logger.debug2('<<< topic_query (%s) from %s', topic, node)
        nodes = self.topic_table.get_nodes(topic)
        self.send_topic_nodes(node, message_hash, nodes)

    def recv_topic_nodes(self, node: kademlia.Node, payload: Tuple[Any, ...],
                         _: Hash32, _m: bytes) -> None:
        echo, raw_nodes = payload
        nodes = _extract_nodes_from_payload(node.address, raw_nodes, self.logger)
        self.logger.debug2('<<< topic_nodes from %s: %s', node, nodes)
        try:
            callback = self.topic_nodes_callbacks.get_callback(node)
        except KeyError:
            self.logger.debug(
                'Unexpected topic_nodes from %s, probably came too late', node)
        else:
            callback(echo, nodes)

    def send_ping_v5(self, node: kademlia.Node, topics: List[bytes]) -> Hash32:
        version = rlp.sedes.big_endian_int.serialize(PROTO_VERSION_V5)
        payload = (
            version, self.address.to_endpoint(), node.address.to_endpoint(),
            _get_msg_expiration(), topics)
        message = _pack_v5(CMD_PING_V5.id, payload, self.privkey)
        token = self.send_v5(node, message)
        self.logger.debug2('>>> ping (v5) %s (token == %s)', node, encode_hex(token))
        # Return the msg hash, which is used as a token to identify pongs.
        return token

    def send_pong_v5(
            self, node: kademlia.Node, token: Hash32, topic_hash: Hash32,
            ticket_serial: int, wait_periods: List[int]) -> None:
        self.logger.debug2('>>> pong (v5) %s', node)
        payload = (
            node.address.to_endpoint(), token, _get_msg_expiration(), topic_hash, ticket_serial,
            wait_periods)
        message = _pack_v5(CMD_PONG_V5.id, payload, self.privkey)
        self.send_v5(node, message)

    def send_find_node_v5(self, node: kademlia.Node, target_node_id: int) -> None:
        node_id = int_to_big_endian(
            target_node_id).rjust(kademlia.k_pubkey_size // 8, b'\0')
        self.logger.debug2('>>> find_node to %s', node)
        message = _pack_v5(CMD_FIND_NODE.id, (node_id, _get_msg_expiration()), self.privkey)
        self.send_v5(node, message)

    def send_topic_query(self, node: kademlia.Node, topic: bytes) -> Hash32:
        self.logger.debug2('>>> topic_query (%s) to %s', topic, node)
        payload = (topic, _get_msg_expiration())
        message = _pack_v5(CMD_TOPIC_QUERY.id, payload, self.privkey)
        return self.send_v5(node, message)

    def send_topic_register(
            self, node: kademlia.Node, topics: List[bytes], idx: int, pong: bytes) -> None:
        if idx >= len(topics):
            raise ValueError(f"Invalid topic idx: {idx}")
        message = _pack_v5(CMD_TOPIC_REGISTER.id, (topics, idx, pong), self.privkey)
        self.logger.debug2('>>> topic_register to %s: %s', node, topics[idx])
        self.send_v5(node, message)

    def send_topic_nodes(
            self, node: kademlia.Node, echo: Hash32, nodes: Tuple[kademlia.Node, ...]) -> None:
        encoded_nodes = tuple(
            n.address.to_endpoint() + [n.pubkey.to_bytes()]
            for n in nodes)
        max_neighbours = self._get_max_neighbours_per_packet()
        for batch in eth_utils.toolz.partition_all(max_neighbours, encoded_nodes):
            message = _pack_v5(CMD_TOPIC_NODES.id, (echo, batch), self.privkey)
            self.logger.debug2('>>> topic_nodes to %s: %s', node, batch)
            self.send_v5(node, message)

    async def wait_topic_nodes(
            self, remote: kademlia.Node, echo: Hash32) -> Tuple[kademlia.Node, ...]:
        """Wait for a topic_nodes msg from the given node.

        Returns the list of nodes received.
        """
        event = asyncio.Event()
        nodes: List[kademlia.Node] = []

        def process(received_echo: Hash32, response: List[kademlia.Node]) -> None:
            if received_echo != echo:
                self.logger.warning(
                    "Unexpected topic_nodes from %s, expected echo %s, got %s",
                    remote, encode_hex(echo), encode_hex(received_echo))
                return

            nodes.extend(response)
            # This callback may be called multiple times if the number of nodes returned by the
            # peer make the msg exceed the 1280 bytes limit, so we only call event.set() once
            # we've received enough neighbours.
            if len(nodes) >= MAX_ENTRIES_PER_TOPIC:
                event.set()

        with self.topic_nodes_callbacks.acquire(remote, process):
            try:
                await self.cancel_token.cancellable_wait(
                    event.wait(), timeout=kademlia.k_request_timeout)
            except TimeoutError:
                # A timeout here just means we didn't get at least MAX_ENTRIES_PER_TOPIC nodes,
                # but we'll still process the ones we get.
                self.logger.debug2(
                    'timed out waiting for %d neighbours from %s', MAX_ENTRIES_PER_TOPIC, remote)
            finally:
                self.logger.debug2('got %d topic nodes from %s', len(nodes), remote)

        return tuple(n for n in nodes if n != self.this_node)

    async def get_ticket(self, node: kademlia.Node, topics: List[bytes]) -> 'Ticket':
        token = self.send_ping_v5(node, topics)
        try:
            got_pong, raw_pong, wait_periods = await self.wait_pong_v5(node, token)
        except AlreadyWaitingDiscoveryResponse:
            raise UnableToGetDiscV5Ticket(
                f"Failed to get ticket from {node}, already waiting for pong")

        if not got_pong:
            raise UnableToGetDiscV5Ticket(f"failed to get ticket from {node}")

        return Ticket(node, raw_pong, topics, wait_periods)

    async def wait_pong_v5(
            self, remote: kademlia.Node, token: Hash32) -> Tuple[bool, bytes, List[float]]:
        event = asyncio.Event()
        wait_periods: List[float] = []
        pong: bytes = None

        def callback(raw_msg: bytes, wps: List[float]) -> None:
            nonlocal pong, wait_periods
            event.set()
            pong = raw_msg
            wait_periods = wps

        got_pong = await self._wait_pong(remote, token, event, callback)
        return got_pong, pong, wait_periods

    def process_pong_v5(self, remote: kademlia.Node, token: Hash32, raw_msg: bytes,
                        wait_periods: List[float]) -> None:
        pingid = self._mkpingid(token, remote)
        try:
            callback = self.pong_callbacks.get_callback(pingid)
        except KeyError:
            self.logger.debug('unexpected v5 pong from %s (token == %s)', remote, encode_hex(token))
        else:
            callback(raw_msg, wait_periods)


class PreferredNodeDiscoveryProtocol(DiscoveryProtocol):
    """
    A DiscoveryProtocol which has a list of preferred nodes which it will prioritize using before
    trying to find nodes.  Each preferred node can only be used once every
    preferred_node_recycle_time seconds.
    """
    preferred_nodes: Sequence[kademlia.Node] = None
    preferred_node_recycle_time: int = 300
    _preferred_node_tracker: Dict[kademlia.Node, float] = None

    def __init__(self,
                 privkey: datatypes.PrivateKey,
                 address: kademlia.Address,
                 bootstrap_nodes: Tuple[kademlia.Node, ...],
                 preferred_nodes: Sequence[kademlia.Node],
                 cancel_token: CancelToken) -> None:
        super().__init__(privkey, address, bootstrap_nodes, cancel_token)

        self.preferred_nodes = preferred_nodes
        self.logger.info('Preferred peers: %s', self.preferred_nodes)
        self._preferred_node_tracker = collections.defaultdict(lambda: 0)

    @to_tuple
    def _get_eligible_preferred_nodes(self) -> Iterator[kademlia.Node]:
        """
        Return nodes from the preferred_nodes which have not been used within
        the last preferred_node_recycle_time
        """
        for node in self.preferred_nodes:
            last_used = self._preferred_node_tracker[node]
            if time.time() - last_used > self.preferred_node_recycle_time:
                yield node

    def _get_random_preferred_node(self) -> kademlia.Node:
        """
        Return a random node from the preferred list.
        """
        eligible_nodes = self._get_eligible_preferred_nodes()
        if not eligible_nodes:
            raise NoEligibleNodes("No eligible preferred nodes available")
        node = random.choice(eligible_nodes)
        return node

    def get_random_bootnode(self) -> Iterator[kademlia.Node]:
        """
        Return a single node to bootstrap, preferring nodes from the preferred list.
        """
        try:
            node = self._get_random_preferred_node()
            self._preferred_node_tracker[node] = time.time()
            yield node
        except NoEligibleNodes:
            yield from super().get_random_bootnode()

    def get_nodes_to_connect(self, count: int) -> Iterator[kademlia.Node]:
        """
        Return up to `count` nodes, preferring nodes from the preferred list.
        """
        preferred_nodes = self._get_eligible_preferred_nodes()[:count]
        for node in preferred_nodes:
            self._preferred_node_tracker[node] = time.time()
            yield node

        num_nodes_needed = max(0, count - len(preferred_nodes))
        yield from super().get_nodes_to_connect(num_nodes_needed)


class DiscoveryByTopicProtocol(DiscoveryProtocol):
    """Experimental discovery implementation that uses topic_query to find compatible nodes"""
    use_v5 = True
    _concurrent_topic_nodes_requests = 10

    def __init__(self,
                 topic: bytes,
                 privkey: datatypes.PrivateKey,
                 address: kademlia.Address,
                 bootstrap_nodes: Tuple[kademlia.Node, ...],
                 cancel_token: CancelToken) -> None:
        super().__init__(privkey, address, bootstrap_nodes, cancel_token)
        self.topic = topic

    def get_nodes_to_connect(self, count: int) -> Iterator[kademlia.Node]:
        topic_nodes = self.topic_table.get_nodes(self.topic)
        for node in topic_nodes:
            yield node

        num_nodes_needed = max(0, count - len(topic_nodes))
        yield from super().get_nodes_to_connect(num_nodes_needed)

    async def lookup_random(self) -> Tuple[kademlia.Node, ...]:
        query_nodes = list(self.routing.get_random_nodes(self._concurrent_topic_nodes_requests))
        expected_echoes = tuple(
            (n, self.send_topic_query(n, self.topic))
            for n in query_nodes)
        replies = await asyncio.gather(
            *[self.wait_topic_nodes(n, echo) for n, echo in expected_echoes])
        seen_nodes = set(eth_utils.toolz.concat(replies))
        self.logger.debug(
            "Got %d nodes for the %s topic: %s", len(seen_nodes), self.topic, seen_nodes)
        for node in seen_nodes:
            self.topic_table.add_node(node, self.topic)

        if len(seen_nodes) < kademlia.k_bucket_size:
            # Not enough nodes were found for our topic, so perform a regular kademlia lookup for
            # a random node ID.
            extra_nodes = await super().lookup_random()
            seen_nodes.update(extra_nodes)

        return tuple(seen_nodes)


class StaticDiscoveryService(BaseService):
    """A 'discovery' service that only connects to the given nodes"""

    def __init__(
            self,
            event_bus: AsyncioEndpoint,
            static_peers: Tuple[KademliaNode, ...],
            token: CancelToken = None) -> None:
        super().__init__(token)
        self._event_bus = event_bus
        self._static_peers = static_peers

    async def handle_get_peer_candidates_requests(self) -> None:
        async for event in self._event_bus.stream(PeerCandidatesRequest):
            candidates = self._select_nodes(event.max_candidates)
            await self._broadcast_nodes(event, candidates)

    async def handle_get_random_bootnode_requests(self) -> None:
        async for event in self._event_bus.stream(RandomBootnodeRequest):
            candidates = self._select_nodes(1)
            await self._broadcast_nodes(event, candidates)

    def _select_nodes(self, max_nodes: int) -> Tuple[KademliaNode, ...]:
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
            nodes: Tuple[KademliaNode, ...]) -> None:
        await self._event_bus.broadcast(
            event.expected_response_type()(nodes),
            event.broadcast_config()
        )

    async def _run(self) -> None:
        self.run_daemon_task(self.handle_get_peer_candidates_requests())
        self.run_daemon_task(self.handle_get_random_bootnode_requests())

        await self.cancel_token.wait()


class NoopDiscoveryService(BaseService):
    'A stub "discovery service" which does nothing'

    def __init__(self, event_bus: AsyncioEndpoint, token: CancelToken = None) -> None:
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
                 event_bus: AsyncioEndpoint,
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

    def __init__(self, logger: ExtendedDebugLogger) -> None:
        self.logger = logger
        # A per-topic FIFO set of nodes.
        self.topics: Dict[bytes, 'collections.OrderedDict[kademlia.Node, float]'] = (
            collections.defaultdict(collections.OrderedDict))
        # The IDs of the last issued/used tickets for any given node.
        self.node_tickets: Dict[kademlia.Node, NodeTicketInfo] = {}

    def add_node(self, node: kademlia.Node, topic: bytes) -> None:
        entries = self.topics[topic]
        if node in entries:
            entries.pop(node)
        while len(entries) >= MAX_ENTRIES_PER_TOPIC:
            entries.popitem(last=False)
        entries[node] = time.time() + self.registration_lifetime

    def get_nodes(self, topic: bytes) -> Tuple[kademlia.Node, ...]:
        if topic not in self.topics:
            return tuple()
        else:
            now = time.time()
            entries = [(node, expiry) for node, expiry in self.topics[topic].items()
                       if expiry > now]
            self.topics[topic] = collections.OrderedDict(entries)
            return tuple(node for node, _ in entries)

    def use_ticket(self, node: kademlia.Node, ticket_serial: int, topic: bytes) -> None:
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

    def issue_ticket(self, node: kademlia.Node) -> int:
        node_info = self.node_tickets.setdefault(node, NodeTicketInfo())
        node_info.last_issued += 1
        return node_info.last_issued


class Ticket:

    def __init__(self, node: kademlia.Node, pong: bytes, topics: List[bytes],
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
        sender: kademlia.Address,
        payload: List[Tuple[str, bytes, bytes, bytes]],
        logger: ExtendedDebugLogger) -> Iterator[kademlia.Node]:
    for item in payload:
        ip, udp_port, tcp_port, node_id = item
        address = kademlia.Address.from_endpoint(ip, udp_port, tcp_port)
        if kademlia.check_relayed_addr(sender, address):
            yield kademlia.Node(keys.PublicKey(node_id), address)
        else:
            logger.debug("Skipping invalid address %s relayed by %s", address, sender)


def _get_max_neighbours_per_packet() -> int:
    # As defined in https://github.com/ethereum/devp2p/blob/master/rlpx.md, the max size of a
    # datagram must be 1280 bytes, so when sending neighbours packets we must include up to
    # _max_neighbours_per_packet and if there's more than that split them across multiple
    # packets.
    # Use an IPv6 address here as we're interested in the size of the biggest possible node
    # representation.
    addr = kademlia.Address('::1', 30303, 30303)
    node_data = addr.to_endpoint() + [b'\x00' * (kademlia.k_pubkey_size // 8)]
    neighbours = [node_data]
    expiration = rlp.sedes.big_endian_int.serialize(_get_msg_expiration())
    payload = rlp.encode([neighbours] + [expiration])
    while HEAD_SIZE + len(payload) <= 1280:
        neighbours.append(node_data)
        payload = rlp.encode([neighbours] + [expiration])
    return len(neighbours) - 1


def _pack_v4(cmd_id: int, payload: Tuple[Any, ...], privkey: datatypes.PrivateKey) -> bytes:
    """Create and sign a UDP message to be sent to a remote node.

    See https://github.com/ethereum/devp2p/blob/master/rlpx.md#node-discovery for information on
    how UDP packets are structured.
    """
    cmd_id = to_bytes(cmd_id)
    expiration = rlp.sedes.big_endian_int.serialize(_get_msg_expiration())
    encoded_data = cmd_id + rlp.encode(payload + tuple([expiration]))
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
    cmd = CMD_ID_MAP[cmd_id]
    payload = tuple(rlp.decode(message[HEAD_SIZE + 1:], strict=False))
    # Ignore excessive list elements as required by EIP-8.
    payload = payload[:cmd.elem_count]
    return remote_pubkey, cmd_id, payload, message_hash


def _get_msg_expiration() -> int:
    return int(time.time() + EXPIRATION)


def _pack_v5(cmd_id: int, payload: Tuple[Any, ...], privkey: datatypes.PrivateKey) -> bytes:
    """Create and sign a discovery v5 UDP message to be sent to a remote node."""
    cmd_id = to_bytes(cmd_id)
    encoded_data = cmd_id + rlp.encode(payload)
    signature = privkey.sign_msg(encoded_data)
    return signature.to_bytes() + encoded_data


def _unpack_v5(message: bytes) -> Tuple[datatypes.PublicKey, int, Tuple[Any, ...], Hash32]:
    """Unpack a discovery v5 UDP message received from a remote node.

    Returns the public key used to sign the message, the cmd ID, payload and msg hash.
    """
    if not message.startswith(V5_ID_STRING):
        raise DefectiveMessage("Missing v5 version prefix")
    message_hash = keccak(message[len(V5_ID_STRING):])
    signature = keys.Signature(message[len(V5_ID_STRING):HEAD_SIZE_V5])
    body = message[HEAD_SIZE_V5:]
    remote_pubkey = signature.recover_public_key_from_msg(body)
    cmd_id = body[0]
    cmd = CMD_ID_MAP_V5[cmd_id]
    payload = tuple(rlp.decode(body[1:], strict=False))
    # Ignore excessive list elements as required by EIP-8.
    payload = payload[:cmd.elem_count]
    return remote_pubkey, cmd_id, payload, message_hash


class CallbackLock:
    def __init__(self,
                 callback: Callable[..., Any],
                 timeout: float=2 * kademlia.k_request_timeout) -> None:
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


def get_v5_topic(proto: Type[protocol.Protocol], genesis_hash: Hash32) -> bytes:
    proto_id = proto.name.upper()
    if proto.version != 1:
        proto_id += str(proto.version)
    topic = proto_id + '@' + remove_0x_prefix(encode_hex(genesis_hash[:8]))
    return topic.encode('ascii')


def _test() -> None:
    import argparse
    import signal
    from p2p import constants
    from p2p import ecies

    loop = asyncio.get_event_loop()
    loop.set_debug(True)

    parser = argparse.ArgumentParser()
    parser.add_argument('-bootnode', type=str, help="The enode to use as bootnode")
    parser.add_argument('-v5', action="store_true")
    parser.add_argument('-trace', action="store_true")
    args = parser.parse_args()

    log_level = logging.DEBUG
    if args.trace:
        log_level = DEBUG2_LEVEL_NUM
    logging.basicConfig(level=log_level, format='%(asctime)s %(levelname)s: %(message)s')

    listen_host = '127.0.0.1'
    # Listen on a port other than 30303 so that we can test against a local geth instance
    # running on that port.
    listen_port = 30304
    privkey = ecies.generate_privkey()
    addr = kademlia.Address(listen_host, listen_port, listen_port)
    if args.bootnode:
        bootstrap_nodes = tuple([kademlia.Node.from_uri(args.bootnode)])
    elif args.v5:
        bootstrap_nodes = tuple(
            kademlia.Node.from_uri(enode) for enode in constants.DISCOVERY_V5_BOOTNODES)
    else:
        bootstrap_nodes = tuple(
            kademlia.Node.from_uri(enode) for enode in constants.ROPSTEN_BOOTNODES)

    cancel_token = CancelToken("discovery")
    if args.v5:
        # topic = b'LES2@41941023680923e0'  # LES2/ropsten
        topic = b'LES2@d4e56740f876aef8'  # LES2/mainnet
        discovery: DiscoveryProtocol = DiscoveryByTopicProtocol(
            topic, privkey, addr, bootstrap_nodes, cancel_token)
    else:
        discovery = DiscoveryProtocol(privkey, addr, bootstrap_nodes, cancel_token)

    async def run() -> None:
        await loop.create_datagram_endpoint(lambda: discovery, local_addr=('0.0.0.0', listen_port))
        try:
            await discovery.bootstrap()
            if args.v5:
                while True:
                    nodes = discovery.topic_table.get_nodes(topic)
                    print("******* %d topic nodes found ***************" % len(nodes))
                    print(nodes)
                    await discovery.lookup_random()
                    await cancel_token.cancellable_wait(asyncio.sleep(5))
        except OperationCancelled:
            pass
        finally:
            await discovery.stop()

    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, discovery.cancel_token.trigger)

    loop.run_until_complete(run())
    loop.close()


if __name__ == "__main__":
    _test()
