"""
The Node Discovery protocol provides a way to find RLPx nodes that can be connected to. It uses a
Kademlia-like protocol to maintain a distributed database of the IDs and endpoints of all
listening nodes.

More information at https://github.com/ethereum/devp2p/blob/master/rlpx.md#node-discovery
"""
import asyncio
import copy
import logging
import os
import sha3
import time
from typing import (
    Any,
    AnyStr,
    Callable,
    Generator,
    List,
    Tuple
)

import rlp
from eth_utils import (
    decode_hex,
    force_bytes,
    to_list,
)

from eth_keys import keys
from eth_keys import datatypes

from evm.p2p import kademlia
from evm.utils.keccak import keccak
from evm.utils.numeric import (
    big_endian_to_int,
    int_to_big_endian,
    safe_ord,
)

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


class Command():
    def __init__(self, name: str, id: int, elem_count: int) -> None:
        self.name = name
        self.id = id
        # Number of required top-level list elements for this cmd.
        # Elements beyond this length must be trimmed.
        self.elem_count = elem_count

    def __repr__(self):
        return 'Command(%s:%d)' % (self.name, self.id)


CMD_PING = Command("ping", 1, 5)
CMD_PONG = Command("pong", 2, 6)
CMD_FIND_NODE = Command("find_node", 3, 2)
CMD_NEIGHBOURS = Command("neighbours", 4, 2)
CMD_TOPIC_QUERY = Command("topic_query", 7, 2)
CMD_TOPIC_NODES = Command("topic_nodes", 8, 2)
CMD_ID_MAP = dict(
    (cmd.id, cmd)
    for cmd in [
        CMD_PING, CMD_PONG, CMD_FIND_NODE, CMD_NEIGHBOURS, CMD_TOPIC_QUERY, CMD_TOPIC_NODES])


class DiscoveryProtocol(asyncio.DatagramProtocol):
    """A Kademlia-like protocol to discover RLPx nodes."""
    logger = logging.getLogger("evm.p2p.discovery.DiscoveryProtocol")
    transport = None  # type: asyncio.DatagramTransport
    _max_neighbours_per_packet_cache = None

    def __init__(self, privkey: datatypes.PrivateKey, address: kademlia.Address,
                 bootstrap_nodes: List[kademlia.Node],
                 topic: bytes) -> None:
        self.privkey = privkey
        self.address = address
        self.bootstrap_nodes = bootstrap_nodes
        self.topic = topic
        self.this_node = kademlia.Node(self.pubkey, address)
        self.kademlia = kademlia.KademliaProtocol(self.this_node, wire=self)
        # XXX: Dirty hack to keep track of nodes that have a matching topic with us
        self.matching_nodes = set()
        self.queried_nodes = {}

    @property
    def pubkey(self) -> datatypes.PublicKey:
        return self.privkey.public_key

    def _get_handler(self, cmd) -> Callable[[kademlia.Node, List[Any], AnyStr], None]:
        if cmd == CMD_PING:
            return self.recv_ping
        elif cmd == CMD_PONG:
            return self.recv_pong
        elif cmd == CMD_FIND_NODE:
            return self.recv_find_node
        elif cmd == CMD_NEIGHBOURS:
            return self.recv_neighbours
        elif cmd == CMD_TOPIC_NODES:
            return self.recv_topic_nodes
        else:
            # XXX: Temporary, while we don't support all discv5 commands
            # raise ValueError("Unknown command: %s", cmd)
            self.logger.debug('no handler for discv5 command %s', cmd)
            return lambda *args: None

    def _get_max_neighbours_per_packet(self):
        if self._max_neighbours_per_packet_cache is not None:
            return self._max_neighbours_per_packet_cache
        self._max_neighbours_per_packet_cache = _get_max_neighbours_per_packet()
        return self._max_neighbours_per_packet_cache

    async def listen(self, loop: asyncio.AbstractEventLoop) -> Tuple[
            asyncio.BaseTransport, asyncio.BaseProtocol]:
        return await loop.create_datagram_endpoint(
            lambda: self, local_addr=(self.address.ip, self.address.udp_port))

    def connection_made(self, transport):
        self.transport = transport

    async def run(self):
        """Loop forever, trying to find new peers that support our topic.

        This is a bit of a hack, just to experiment with discv5's topic-search functionality.
        """
        await self.listen(asyncio.get_event_loop())
        bonded = await asyncio.gather(*[self.kademlia.bond(n) for n in self.bootstrap_nodes])
        if not any(bonded):
            self.logger.warn("Failed to bond with bootstrap nodes {}".format(self.bootstrap_nodes))
            # TODO: Must raise or call sys.exit
            return

        topic_hash = sha3.keccak_256(self.topic).digest()
        while True:
            target = big_endian_to_int(topic_hash[:8] + os.urandom(24))
            try:
                nodes = await self.kademlia.lookup(target)
            except kademlia.AlreadyWaiting as e:
                self.logger.warn("Error when looking up: %s", e)
                continue
            for node in nodes:
                now = time.time()
                last_query = self.queried_nodes.get(node)
                if last_query is not None and last_query > (now - (60 * 60)):
                    continue
                self.queried_nodes[node] = time.time()
                self.send_topic_query(node)
            self.logger.info(
                "Nodes with matching topics: %s",
                [(n.pubkey.to_bytes(), n.address) for n in self.matching_nodes])
            await asyncio.sleep(5)

    async def bootstrap(self):
        while self.transport is None:
            # FIXME: Instead of sleeping here to wait until connection_made() is called to set
            # .transport we should instead only call it after we know it's been set.
            await asyncio.sleep(1)
        self.logger.debug("boostrapping with {}".format(self.bootstrap_nodes))
        await self.kademlia.bootstrap(self.bootstrap_nodes)

    # FIXME: Enable type checking here once we have a mypy version that
    # includes the fix for https://github.com/python/typeshed/pull/1740
    def datagram_received(self, data: AnyStr, addr: Tuple[str, int]) -> None:  # type: ignore
        ip_address, udp_port = addr
        self.receive(kademlia.Address(ip_address, udp_port), data)  # type: ignore

    def error_received(self, exc: Exception) -> None:
        self.logger.error('error received: {}'.format(exc))

    def send(self, node: kademlia.Node, message: bytes) -> None:
        self.transport.sendto(message, (node.address.ip, node.address.udp_port))

    def stop(self):
        self.logger.info('stopping discovery')
        self.transport.close()

    def receive(self, address: kademlia.Address, message: AnyStr) -> None:
        # XXX: Quick hack while we don't support all of discv5 commands
        cmd_id = safe_ord(message[HEAD_SIZE])
        if cmd_id not in CMD_ID_MAP:
            self.logger.debug('ignoring msg with unsupported cmd id: %d', cmd_id)
            return

        try:
            remote_pubkey, cmd_id, payload, message_hash = _unpack(message)
        except DefectiveMessage as e:
            self.logger.error('error unpacking message: {}'.format(e))
            return

        # XXX: Commented out as on v5 the expiration is not always the last element.
        # As of discovery version 4, expiration is the last element for all packets, so
        # we can validate that here, but if it changes we may have to do so on the
        # handler methods.
        # expiration = rlp.sedes.big_endian_int.deserialize(payload[-1])
        # if time.time() > expiration:
        #     self.logger.error('received message already expired')
        #     return

        cmd = CMD_ID_MAP[cmd_id]
        if len(payload) != cmd.elem_count:
            self.logger.error('invalid %s payload: %s', cmd.name, payload)
            return
        node = kademlia.Node(remote_pubkey, address)
        handler = self._get_handler(cmd)
        handler(node, payload, message_hash)

    def recv_pong(self, node: kademlia.Node, payload: List[Any], _: AnyStr) -> None:
        # The pong payload should have 6 elements: to, token, expiration, topic_hash,
        # ticket_serial and wait_periods
        _, token, _, topic_hash, ticket_serial, wait_periods = payload
        self.kademlia.recv_pong(node, token)

    def recv_neighbours(self, node: kademlia.Node, payload: List[Any], _: AnyStr) -> None:
        # The neighbours payload should have 2 elements: nodes, expiration
        nodes, _ = payload
        self.kademlia.recv_neighbours(node, _extract_nodes_from_payload(nodes))

    def recv_ping(self, remote: kademlia.Node, payload: List[Any], message_hash: AnyStr) -> None:
        _, _, _, _, topics = payload
        self.kademlia.recv_ping(remote, message_hash, topics)
        # self.send_topic_query(remote)

    def recv_find_node(self, node: kademlia.Node, payload: List[Any], _: AnyStr) -> None:
        # The find_node payload should have 2 elements: node_id, expiration
        self.logger.debug('<<< find_node from {}'.format(node))
        node_id, _ = payload
        self.kademlia.recv_find_node(node, big_endian_to_int(node_id))

    def recv_topic_nodes(self, remote: kademlia.Node, payload: List[Any], _: AnyStr) -> None:
        echo, raw_nodes = payload
        nodes = _extract_nodes_from_payload(raw_nodes)
        self.logger.debug('<<< topic_nodes from %s: %s', remote, nodes)
        for node in nodes:
            # XXX: Discovery v5 (while in test mode) runs on UDPport+1, so need to adjust that
            # here.
            # https://github.com/ethereum/go-ethereum/blob/bf62acf0332c962916787a23c78a2513137625ea/p2p/discv5/ticket.go#L646
            addr = copy.copy(node.address)
            addr.udp_port -= 1
            addr.tcp_port -= 1
            self.matching_nodes.add(kademlia.Node(node.pubkey, addr))
            self.send_ping(node)
            self.send_topic_query(node)

    def send_topic_query(self, remote: kademlia.Node) -> None:
        self.logger.debug('>>> topic_query to %s', remote)
        payload = [
            self.topic,
            int(time.time() + EXPIRATION),
        ]
        message = _pack(CMD_TOPIC_QUERY.id, payload, self.privkey)
        self.send(remote, message)

    def send_ping(self, node: kademlia.Node) -> bytes:
        self.logger.debug('>>> pinging {}'.format(node))
        version = rlp.sedes.big_endian_int.serialize(PROTO_VERSION)
        payload = [
            version,
            self.address.to_endpoint(),
            node.address.to_endpoint(),
            int(time.time() + EXPIRATION),
            [self.topic]
        ]
        message = _pack(CMD_PING.id, payload, self.privkey)
        self.send(node, message)
        # Return the msg hash, which is used as a token to identify pongs.
        return message[:MAC_SIZE]

    def send_find_node(self, node: kademlia.Node, target_node_id: int) -> None:
        target_node_id = int_to_big_endian(
            target_node_id).rjust(kademlia.k_pubkey_size // 8, b'\0')
        self.logger.debug('>>> find_node to {}'.format(node))
        payload = [
            target_node_id,
            int(time.time() + EXPIRATION),
        ]
        message = _pack(CMD_FIND_NODE.id, payload, self.privkey)
        self.send(node, message)

    def send_pong(self, node: kademlia.Node, token: AnyStr, topics) -> None:
        self.logger.debug('>>> ponging {}'.format(node))
        h = sha3.keccak_256()
        h.update(rlp.encode(topics))
        topic_hash = h.digest()
        # XXX: No idea what would be "correct" values for those
        ticket_serial = 0
        wait_periods = [60]
        payload = [
            node.address.to_endpoint(),
            token,
            int(time.time() + EXPIRATION),
            topic_hash,
            ticket_serial,
            wait_periods,
        ]
        message = _pack(CMD_PONG.id, payload, self.privkey)
        self.send(node, message)

    def send_neighbours(self, node: kademlia.Node, neighbours: List[kademlia.Node]) -> None:
        nodes = []
        neighbours = sorted(neighbours)
        for n in neighbours:
            nodes.append(n.address.to_endpoint() + [n.pubkey.to_bytes()])

        max_neighbours = self._get_max_neighbours_per_packet()
        for i in range(0, len(nodes), max_neighbours):
            message = _pack(CMD_NEIGHBOURS.id, [nodes[i:i + max_neighbours]], self.privkey)
            self.logger.debug('>>> neighbours to {}: {}'.format(
                node, neighbours[i:i + max_neighbours]))
            self.send(node, message)


@to_list
def _extract_nodes_from_payload(
        payload: List[Tuple[str, str, str, str]]) -> Generator[kademlia.Node, None, None]:
    for item in payload:
        ip, udp_port, tcp_port, node_id = item
        address = kademlia.Address.from_endpoint(ip, udp_port, tcp_port)
        yield kademlia.Node(keys.PublicKey(node_id), address)


def _get_max_neighbours_per_packet():
    # As defined in https://github.com/ethereum/devp2p/blob/master/rlpx.md, the max size of a
    # datagram must be 1280 bytes, so when sending neighbours packets we must include up to
    # _max_neighbours_per_packet and if there's more than that split them across multiple
    # packets.
    # Use an IPv6 address here as we're interested in the size of the biggest possible node
    # representation.
    addr = kademlia.Address('::1', 30303, 30303)
    node_data = addr.to_endpoint() + [b'\x00' * (kademlia.k_pubkey_size // 8)]
    neighbours = [node_data]
    expiration = rlp.sedes.big_endian_int.serialize(int(time.time() + EXPIRATION))
    payload = rlp.encode([neighbours] + [expiration])
    while HEAD_SIZE + len(payload) <= 1280:
        neighbours.append(node_data)
        payload = rlp.encode([neighbours] + [expiration])
    return len(neighbours) - 1


def _pack(cmd_id: int, payload: List[Any], privkey: datatypes.PrivateKey) -> bytes:
    """Create and sign a UDP message to be sent to a remote node.

    See https://github.com/ethereum/devp2p/blob/master/rlpx.md#node-discovery for information on
    how UDP packets are structured.
    """
    cmd_id = force_bytes(chr(cmd_id))
    # expiration = rlp.sedes.big_endian_int.serialize(int(time.time() + EXPIRATION))
    encoded_data = cmd_id + rlp.encode(payload)
    signature = privkey.sign_msg(encoded_data)
    message_hash = keccak(signature.to_bytes() + encoded_data)
    return message_hash + signature.to_bytes() + encoded_data


def _unpack(message: AnyStr) -> Tuple[datatypes.PublicKey, int, List[Any], AnyStr]:
    """Unpack a UDP message received from a remote node.

    Returns the public key used to sign the message, the cmd ID, payload and hash.
    """
    message_hash = message[:MAC_SIZE]
    if message_hash != keccak(message[MAC_SIZE:]):
        raise WrongMAC()
    signature = keys.Signature(message[MAC_SIZE:HEAD_SIZE])
    signed_data = message[HEAD_SIZE:]
    remote_pubkey = signature.recover_public_key_from_msg(signed_data)
    cmd_id = safe_ord(message[HEAD_SIZE])
    cmd = CMD_ID_MAP[cmd_id]
    payload = rlp.decode(message[HEAD_SIZE + 1:], strict=False)
    # Ignore excessive list elements as required by EIP-8.
    payload = payload[:cmd.elem_count]
    return remote_pubkey, cmd_id, payload, message_hash


if __name__ == "__main__":
    async def show_tasks():
        while True:
            tasks = []
            for task in asyncio.Task.all_tasks():
                if task._coro.__name__ != "show_tasks":
                    tasks.append(task._coro.__name__)
            if tasks:
                logger.debug("Active tasks: {}".format(tasks))
            await asyncio.sleep(3)

    privkey_hex = '65462b0520ef7d3df61b9992ed3bea0c56ead753be7c8b3614e0ce01e4cac41b'
    listen_host = '0.0.0.0'
    listen_port = 30303
    bootstrap_uris = [
        # Discv5 topic discovery bootnode
        b"enode://0cc5f5ffb5d9098c8b8c62325f3797f56509bff942704687b6530992ac706e2cb946b90a34f1f19548cd3c7baccbcaea354531e5983c7d1bc0dee16ce4b6440b@40.118.3.223:30305",  # noqa: E501
        # b"enode://1c7a64d76c0334b0418c004af2f67c50e36a3be60b5e4790bdac0439d21603469a85fad36f2473c9a80eb043ae60936df905fa28f1ff614c3e5dc34f15dcd2dc@40.118.3.223:30308",  # noqa: E501
        # b"enode://85c85d7143ae8bb96924f2b54f1b3e70d8c4d367af305325d30a61385a432f247d2c75c45c6b4a60335060d072d7f5b35dd1d4c45f76941f62a4f83b6e75daaf@40.118.3.223:30309",  # noqa: E501
        # Local geth bootnodes
        # b'enode://3a514176466fa815ed481ffad09110a2d344f6c9b78c1d14afc351c3a51be33d8072e77939dc03ba44790779b7a1025baf3003f6732430e20cd9b76d953391b3@0.0.0.0:30304',  # noqa: E501
        # Testnet bootnodes
        # b'enode://6ce05930c72abc632c58e2e4324f7c7ea478cec0ed4fa2528982cf34483094e9cbc9216e7aa349691242576d552a2a56aaeae426c5303ded677ce455ba1acd9d@13.84.180.240:30304',  # noqa: E501
        # b'enode://20c9ad97c081d63397d7b685a412227a40e23c8bdc6688c6f37e97cfbc22d2b4d1db1510d8f61e6a8866ad7f0e17c02b14182d37ea7c3c8b9c2683aeb6b733a1@52.169.14.227:30304',  # noqa: E501
        # Mainnet bootnodes
        # b'enode://a979fb575495b8d6db44f750317d0f4622bf4c2aa3365d6af7c284339968eef29b69ad0dce72a4d8db5ebb4968de0e3bec910127f134779fbcb0cb6d3331163c@52.16.188.185:30303',  # noqa: E501
        # b'enode://3f1d12044546b76342d59d4a05532c14b85aa669704bfe1f864fe079415aa2c02d743e03218e57a33fb94523adb54032871a6c51b2cc5514cb7c7e35b3ed0a99@13.93.211.84:30303',  # noqa: E501
        # b'enode://78de8a0916848093c73790ead81d1928bec737d565119932b98c6b100d944b7a95e94f847f689fc723399d2e31129d182f7ef3863f2b4c820abbf3ab2722344d@191.235.84.50:30303',  # noqa: E501
        # b'enode://158f8aab45f6d19c6cbf4a089c2670541a8da11978a2f90dbf6a502a4a3bab80d288afdbeb7ec0ef6d92de563767f3b1ea9e8e334ca711e9f8e2df5a0385e8e6@13.75.154.138:30303',  # noqa: E501
        # b'enode://1118980bf48b0a3640bdba04e0fe78b1add18e1cd99bf22d53daac1fd9972ad650df52176e7c7d89d1114cfef2bc23a2959aa54998a46afcf7d91809f0855082@52.74.57.123:30303',   # noqa: E501
    ]

    # LES@ + <first 8 bytes of genesis hash>, hex encoded
    topic = b'LES@41941023680923e0'  # LES/ropsten
    # topic = b"LES@d4e56740f876aef8"  # LES/mainnet

    logger = logging.getLogger("evm.p2p.discovery")
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    loop = asyncio.get_event_loop()
    loop.set_debug(True)

    privkey = keys.PrivateKey(decode_hex(privkey_hex))
    addr = kademlia.Address(listen_host, listen_port, listen_port)
    bootstrap_nodes = [kademlia.Node.from_uri(x) for x in bootstrap_uris]
    discovery = DiscoveryProtocol(privkey, addr, bootstrap_nodes, topic)

    try:
        loop.run_until_complete(discovery.run())
    except KeyboardInterrupt:
        pass

    # task_monitor.set_result(None)
    discovery.stop()
    # logger.info("Pending tasks at exit: {}".format(asyncio.Task.all_tasks(loop)))
    loop.close()
