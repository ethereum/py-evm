"""
The Node Discovery protocol provides a way to find RLPx nodes that can be connected to. It uses a
Kademlia-like protocol to maintain a distributed database of the IDs and endpoints of all
listening nodes.

More information at https://github.com/ethereum/devp2p/blob/master/rlpx.md#node-discovery
"""
import asyncio
import collections
import logging
import random
import socket
import time
from typing import (
    Any,
    Callable,
    cast,
    Dict,
    Iterator,
    List,
    Sequence,
    Tuple,
    Text,
    Union,
)

import rlp

from eth_typing import Hash32

from eth_utils import (
    encode_hex,
    text_if_str,
    to_bytes,
    to_list,
    to_tuple,
    int_to_big_endian,
    big_endian_to_int,
)

from eth_keys import keys
from eth_keys import datatypes

from eth_hash.auto import keccak

from eth.tools.logging import TraceLogger, TRACE_LEVEL_NUM

from cancel_token import CancelToken, OperationCancelled

from p2p.exceptions import NoEligibleNodes
from p2p import kademlia
from p2p.peer import PeerPool
from p2p.service import BaseService

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
    logger: TraceLogger = cast(TraceLogger, logging.getLogger("p2p.discovery.DiscoveryProtocol"))
    transport: asyncio.DatagramTransport = None
    _max_neighbours_per_packet_cache = None

    def __init__(self,
                 privkey: datatypes.PrivateKey,
                 address: kademlia.Address,
                 bootstrap_nodes: Tuple[kademlia.Node, ...]) -> None:
        self.privkey = privkey
        self.address = address
        self.bootstrap_nodes = bootstrap_nodes
        self.this_node = kademlia.Node(self.pubkey, address)
        self.kademlia = kademlia.KademliaProtocol(self.this_node, wire=self)
        self.cancel_token = CancelToken('DiscoveryProtocol')

    async def lookup_random(self, cancel_token: CancelToken) -> List[kademlia.Node]:
        return await self.kademlia.lookup_random(self.cancel_token.chain(cancel_token))

    def get_random_bootnode(self) -> Iterator[kademlia.Node]:
        if self.bootstrap_nodes:
            yield random.choice(self.bootstrap_nodes)
        else:
            self.logger.warning('No bootnodes available')

    def get_nodes_to_connect(self, count: int) -> Iterator[kademlia.Node]:
        return self.kademlia.routing.get_random_nodes(count)

    @property
    def pubkey(self) -> datatypes.PublicKey:
        return self.privkey.public_key

    def _get_handler(self, cmd: DiscoveryCommand
                     ) -> Callable[[kademlia.Node, Tuple[Any, ...], Hash32], None]:
        if cmd == CMD_PING:
            return self.recv_ping
        elif cmd == CMD_PONG:
            return self.recv_pong
        elif cmd == CMD_FIND_NODE:
            return self.recv_find_node
        elif cmd == CMD_NEIGHBOURS:
            return self.recv_neighbours
        else:
            raise ValueError("Unknwon command: {}".format(cmd))

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
        self.logger.info("boostrapping with %s", self.bootstrap_nodes)
        try:
            await self.kademlia.bootstrap(self.bootstrap_nodes, self.cancel_token)
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

    def error_received(self, exc: Exception) -> None:
        self.logger.error('error received: %s', exc)

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

    def recv_pong(self, node: kademlia.Node, payload: Tuple[Any, ...], _: Hash32) -> None:
        # The pong payload should have 3 elements: to, token, expiration
        _, token, _ = payload
        self.logger.trace('<<< pong (v4) from %s (token == %s)', node, encode_hex(token))
        self.kademlia.recv_pong(node, token)

    def recv_neighbours(self, node: kademlia.Node, payload: Tuple[Any, ...], _: Hash32) -> None:
        # The neighbours payload should have 2 elements: nodes, expiration
        nodes, _ = payload
        neighbours = _extract_nodes_from_payload(nodes)
        self.logger.trace('<<< neighbours from %s: %s', node, neighbours)
        self.kademlia.recv_neighbours(node, neighbours)

    def recv_ping(self, node: kademlia.Node, _: Any, message_hash: Hash32) -> None:
        self.logger.trace('<<< ping(v4) from %s', node)
        self.kademlia.recv_ping(node, message_hash)
        self.send_pong(node, message_hash)

    def recv_find_node(self, node: kademlia.Node, payload: Tuple[Any, ...], _: Hash32) -> None:
        # The find_node payload should have 2 elements: node_id, expiration
        self.logger.trace('<<< find_node from %s', node)
        node_id, _ = payload
        self.kademlia.recv_find_node(node, big_endian_to_int(node_id))

    def send_ping(self, node: kademlia.Node) -> Hash32:
        version = rlp.sedes.big_endian_int.serialize(PROTO_VERSION)
        payload = (version, self.address.to_endpoint(), node.address.to_endpoint())
        message = _pack_v4(CMD_PING.id, payload, self.privkey)
        self.send(node, message)
        # Return the msg hash, which is used as a token to identify pongs.
        token = message[:MAC_SIZE]
        self.logger.trace('>>> ping (v4) %s (token == %s)', node, encode_hex(token))
        # XXX: This hack is needed because there are lots of parity 1.10 nodes out there that send
        # the wrong token on pong msgs (https://github.com/paritytech/parity/issues/8038). We
        # should get rid of this once there are no longer too many parity 1.10 nodes out there.
        parity_token = keccak(message[HEAD_SIZE + 1:])
        self.kademlia.parity_pong_tokens[parity_token] = token
        return token

    def send_find_node(self, node: kademlia.Node, target_node_id: int) -> None:
        node_id = int_to_big_endian(
            target_node_id).rjust(kademlia.k_pubkey_size // 8, b'\0')
        self.logger.trace('>>> find_node to %s', node)
        message = _pack_v4(CMD_FIND_NODE.id, tuple([node_id]), self.privkey)
        self.send(node, message)

    def send_pong(self, node: kademlia.Node, token: Hash32) -> None:
        self.logger.trace('>>> pong %s', node)
        payload = (node.address.to_endpoint(), token)
        message = _pack_v4(CMD_PONG.id, payload, self.privkey)
        self.send(node, message)

    def send_neighbours(self, node: kademlia.Node, neighbours: List[kademlia.Node]) -> None:
        nodes = []
        neighbours = sorted(neighbours)
        for n in neighbours:
            nodes.append(n.address.to_endpoint() + [n.pubkey.to_bytes()])

        max_neighbours = self._get_max_neighbours_per_packet()
        for i in range(0, len(nodes), max_neighbours):
            message = _pack_v4(
                CMD_NEIGHBOURS.id, tuple([nodes[i:i + max_neighbours]]), self.privkey)
            self.logger.trace('>>> neighbours to %s: %s',
                              node, neighbours[i:i + max_neighbours])
            self.send(node, message)

    #
    # Discovery v5 specific methods
    #

    def send_v5(self, node: kademlia.Node, message: bytes) -> Hash32:
        msg_hash = keccak(message)
        self.send(node, V5_ID_STRING + message)
        return msg_hash

    def _get_handler_v5(self, cmd: DiscoveryCommand
                        ) -> Callable[[kademlia.Node, Tuple[Any, ...], Hash32], None]:
        if cmd == CMD_PING_V5:
            return self.recv_ping_v5
        elif cmd == CMD_PONG_V5:
            return self.recv_pong_v5
        elif cmd == CMD_FIND_NODE:
            return self.recv_find_node
        elif cmd == CMD_NEIGHBOURS:
            return self.recv_neighbours
        elif cmd == CMD_FIND_NODEHASH:
            return self.recv_find_nodehash
        elif cmd == CMD_TOPIC_REGISTER:
            return self.recv_topic_register
        elif cmd == CMD_TOPIC_QUERY:
            return self.recv_topic_query
        elif cmd == CMD_TOPIC_NODES:
            return self.recv_topic_nodes
        else:
            raise ValueError("Unknwon command: {}".format(cmd))

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
        handler(node, payload, message_hash)

    def recv_ping_v5(
            self, node: kademlia.Node, payload: Tuple[Any, ...], message_hash: Hash32) -> None:
        # version, from, to, expiration, topics
        _, _, _, _, topics = payload
        self.logger.trace('<<< ping(v5) from %s, topics: %s', node, topics)
        self.kademlia.recv_ping(node, message_hash)
        topic_hash = keccak(rlp.encode(topics))
        # TODO: Create a new ticket for the given node and use that in the pong
        ticket_serial = 0
        wait_periods: List[int] = []
        self.send_pong_v5(node, message_hash, topic_hash, ticket_serial, wait_periods)

    def recv_pong_v5(self, node: kademlia.Node, payload: Tuple[Any, ...], _: Hash32) -> None:
        # to, token, expiration, topic_hash, ticket_serial, wait_periods
        _, token, _, _, _, _ = payload
        self.logger.trace('<<< pong (v5) from %s (token == %s)', node, encode_hex(token))
        self.kademlia.recv_pong(node, token)
        # TODO: Create/store ticket(s)

    def recv_find_nodehash(self, node: kademlia.Node, payload: Tuple[Any, ...], _: Hash32) -> None:
        target_hash, _ = payload
        self.logger.trace('<<< find_nodehash from %s, target: %s', node, target_hash)
        # TODO: Reply with a neighbours msg.

    def recv_topic_register(self, node: kademlia.Node, payload: Tuple[Any, ...], _: Hash32) -> None:
        topics, idx, pong = payload
        self.logger.trace('<<< topic_register from %s, topics: %s', node, topics)
        # TODO: Store the ad if it matches the last ticket we issued for this node, and mark the
        # ticket as used.

    def recv_topic_query(self, node: kademlia.Node, payload: Tuple[Any, ...], _: Hash32) -> None:
        topic, _ = payload
        self.logger.trace('<<< topic_query from %s, topic: %s', node, topic)
        # TODO: Lookup nodes matching the given topic and send a topic_nodes msg

    def recv_topic_nodes(self, node: kademlia.Node, payload: Tuple[Any, ...], _: Hash32) -> None:
        echo, raw_nodes = payload
        nodes = _extract_nodes_from_payload(raw_nodes)
        self.logger.trace('<<< topic_nodes from %s: %s', node, nodes)
        # TODO: Match 'echo' against hash of topic_query msg sent to the same node, and store a
        # link from the topic to the nodes.

    def send_ping_v5(self, node: kademlia.Node, topics: List[bytes]) -> Hash32:
        version = rlp.sedes.big_endian_int.serialize(PROTO_VERSION_V5)
        payload = (
            version, self.address.to_endpoint(), node.address.to_endpoint(),
            _get_msg_expiration(), topics)
        message = _pack_v5(CMD_PING_V5.id, payload, self.privkey)
        token = self.send_v5(node, message)
        self.logger.trace('>>> ping (v5) %s (token == %s)', node, encode_hex(token))
        # Return the msg hash, which is used as a token to identify pongs.
        return token

    def send_pong_v5(
            self, node: kademlia.Node, token: Hash32, topic_hash: Hash32,
            ticket_serial: int, wait_periods: List[int]) -> None:
        self.logger.trace('>>> pong (v5) %s', node)
        payload = (
            node.address.to_endpoint(), token, _get_msg_expiration(), topic_hash, ticket_serial,
            wait_periods)
        message = _pack_v5(CMD_PONG_V5.id, payload, self.privkey)
        self.send_v5(node, message)

    def send_find_node_v5(self, node: kademlia.Node, target_node_id: int) -> None:
        node_id = int_to_big_endian(
            target_node_id).rjust(kademlia.k_pubkey_size // 8, b'\0')
        self.logger.trace('>>> find_node to %s', node)
        message = _pack_v5(CMD_FIND_NODE.id, (node_id, _get_msg_expiration()), self.privkey)
        self.send_v5(node, message)

    def send_topic_query(self, node: kademlia.Node, topic: Hash32) -> None:
        self.logger.trace('>>> topic_query to %s', node)
        payload = (topic, _get_msg_expiration())
        message = _pack_v5(CMD_TOPIC_QUERY.id, payload, self.privkey)
        # TODO: Get the msg hash and store it in the ticket store to match against received
        # topic_node msgs.
        self.send_v5(node, message)


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
                 preferred_nodes: Sequence[kademlia.Node]) -> None:
        super().__init__(privkey, address, bootstrap_nodes)

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


class DiscoveryService(BaseService):
    _lookup_running = asyncio.Lock()
    _last_lookup: float = 0
    _lookup_interval: int = 30

    def __init__(self, proto: DiscoveryProtocol, peer_pool: PeerPool,
                 port: int, token: CancelToken = None) -> None:
        super().__init__(token)
        self.proto = proto
        self.peer_pool = peer_pool
        self.port = port

    async def _run(self) -> None:
        await self._start_udp_listener()
        connect_loop_sleep = 2
        self.run_task(self.proto.bootstrap())
        while self.is_operational:
            await self.maybe_connect_to_more_peers()
            await self.sleep(connect_loop_sleep)

    async def _start_udp_listener(self) -> None:
        loop = asyncio.get_event_loop()
        # TODO: Support IPv6 addresses as well.
        await loop.create_datagram_endpoint(
            lambda: self.proto,
            local_addr=('0.0.0.0', self.port),
            family=socket.AF_INET)

    async def maybe_connect_to_more_peers(self) -> None:
        """Connect to more peers if we're not yet maxed out to max_peers"""
        if self.peer_pool.is_full:
            self.logger.debug("Already connected to %s peers; sleeping", len(self.peer_pool))
            return

        self.run_task(self.maybe_lookup_random_node())

        await self.peer_pool.connect_to_nodes(
            self.proto.get_nodes_to_connect(self.peer_pool.max_peers))

        # In some cases (e.g ROPSTEN or private testnets), the discovery table might be full of
        # bad peers so if we can't connect to any peers we try a random bootstrap node as well.
        if not len(self.peer_pool):
            await self.peer_pool.connect_to_nodes(self.proto.get_random_bootnode())

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
                await self.proto.lookup_random(self.cancel_token)
            except OperationCancelled:
                pass
            finally:
                self._last_lookup = time.time()

    async def _cleanup(self) -> None:
        await self.proto.stop()


@to_list
def _extract_nodes_from_payload(
        payload: List[Tuple[str, str, str, str]]) -> Iterator[kademlia.Node]:
    for item in payload:
        ip, udp_port, tcp_port, node_id = item
        address = kademlia.Address.from_endpoint(ip, udp_port, tcp_port)
        yield kademlia.Node(keys.PublicKey(node_id), address)


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
    message_hash = message[:MAC_SIZE]
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
        log_level = TRACE_LEVEL_NUM
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
    discovery = DiscoveryProtocol(privkey, addr, bootstrap_nodes)
    loop.run_until_complete(
        loop.create_datagram_endpoint(lambda: discovery, local_addr=('0.0.0.0', listen_port)))

    async def run() -> None:
        try:
            if args.v5:
                remote = bootstrap_nodes[0]
                topic = b'LES@41941023680923e0'  # LES/ropsten
                token = discovery.send_ping_v5(remote, [topic])
                await discovery.kademlia.wait_pong(remote, token, discovery.cancel_token)
                discovery.send_find_node_v5(remote, random.randint(0, kademlia.k_max_node_id))
                await discovery.kademlia.wait_neighbours(remote, discovery.cancel_token)
            else:
                await discovery.bootstrap()
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
