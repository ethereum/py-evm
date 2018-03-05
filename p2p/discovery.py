"""
The Node Discovery protocol provides a way to find RLPx nodes that can be connected to. It uses a
Kademlia-like protocol to maintain a distributed database of the IDs and endpoints of all
listening nodes.

More information at https://github.com/ethereum/devp2p/blob/master/rlpx.md#node-discovery
"""
import asyncio
import logging
import random
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
    encode_hex,
    keccak,
    to_bytes,
    to_list,
)

from eth_keys import keys
from eth_keys import datatypes

from p2p.cancel_token import CancelToken
from p2p import kademlia
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


CMD_PING = Command("ping", 1, 4)
CMD_PONG = Command("pong", 2, 3)
CMD_FIND_NODE = Command("find_node", 3, 2)
CMD_NEIGHBOURS = Command("neighbours", 4, 2)
CMD_ID_MAP = dict((cmd.id, cmd) for cmd in [CMD_PING, CMD_PONG, CMD_FIND_NODE, CMD_NEIGHBOURS])


class DiscoveryProtocol(asyncio.DatagramProtocol):
    """A Kademlia-like protocol to discover RLPx nodes."""
    logger = logging.getLogger("p2p.discovery.DiscoveryProtocol")
    transport = None  # type: asyncio.DatagramTransport
    _max_neighbours_per_packet_cache = None

    def __init__(self, privkey: datatypes.PrivateKey, address: kademlia.Address,
                 bootstrap_nodes: List[str]) -> None:
        self.privkey = privkey
        self.address = address
        self.bootstrap_nodes = [kademlia.Node.from_uri(node) for node in bootstrap_nodes]
        self.this_node = kademlia.Node(self.pubkey, address)
        self.kademlia = kademlia.KademliaProtocol(self.this_node, wire=self)
        self.cancel_token = CancelToken('DiscoveryProtocol')

    async def lookup_random(self, cancel_token: CancelToken) -> List[kademlia.Node]:
        node_id = random.randint(0, kademlia.k_max_node_id)
        token_chain = self.cancel_token.chain(cancel_token)
        return await self.kademlia.lookup(node_id, token_chain)

    @property
    def pubkey(self) -> datatypes.PublicKey:
        return self.privkey.public_key

    def _get_handler(self, cmd: Command) -> Callable[[kademlia.Node, List[Any], AnyStr], None]:
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

    async def bootstrap(self):
        while self.transport is None:
            # FIXME: Instead of sleeping here to wait until connection_made() is called to set
            # .transport we should instead only call it after we know it's been set.
            await asyncio.sleep(1)
        self.logger.debug("boostrapping with %s", self.bootstrap_nodes)
        await self.kademlia.bootstrap(self.bootstrap_nodes, self.cancel_token)

    # FIXME: Enable type checking here once we have a mypy version that
    # includes the fix for https://github.com/python/typeshed/pull/1740
    def datagram_received(self, data: AnyStr, addr: Tuple[str, int]) -> None:  # type: ignore
        ip_address, udp_port = addr
        self.receive(kademlia.Address(ip_address, udp_port), data)  # type: ignore

    def error_received(self, exc: Exception) -> None:
        self.logger.error('error received: %s', exc)

    def send(self, node: kademlia.Node, message: bytes) -> None:
        self.transport.sendto(message, (node.address.ip, node.address.udp_port))

    def stop(self):
        self.logger.info('stopping discovery')
        self.cancel_token.trigger()
        self.transport.close()

    def receive(self, address: kademlia.Address, message: AnyStr) -> None:
        try:
            remote_pubkey, cmd_id, payload, message_hash = _unpack(message)
        except DefectiveMessage as e:
            self.logger.error('error unpacking message (%s) from %s: %s', message, address, e)
            return

        # As of discovery version 4, expiration is the last element for all packets, so
        # we can validate that here, but if it changes we may have to do so on the
        # handler methods.
        expiration = rlp.sedes.big_endian_int.deserialize(payload[-1])
        if time.time() > expiration:
            self.logger.error('received message already expired')
            return

        cmd = CMD_ID_MAP[cmd_id]
        if len(payload) != cmd.elem_count:
            self.logger.error('invalid %s payload: %s', cmd.name, payload)
            return
        node = kademlia.Node(remote_pubkey, address)
        handler = self._get_handler(cmd)
        handler(node, payload, message_hash)

    def recv_pong(self, node: kademlia.Node, payload: List[Any], _: AnyStr) -> None:
        # The pong payload should have 3 elements: to, token, expiration
        _, token, _ = payload
        self.kademlia.recv_pong(node, token)

    def recv_neighbours(self, node: kademlia.Node, payload: List[Any], _: AnyStr) -> None:
        # The neighbours payload should have 2 elements: nodes, expiration
        nodes, _ = payload
        self.kademlia.recv_neighbours(node, _extract_nodes_from_payload(nodes))

    def recv_ping(self, node: kademlia.Node, _: Any, message_hash: AnyStr) -> None:
        self.kademlia.recv_ping(node, message_hash)

    def recv_find_node(self, node: kademlia.Node, payload: List[Any], _: AnyStr) -> None:
        # The find_node payload should have 2 elements: node_id, expiration
        self.logger.debug('<<< find_node from %s', node)
        node_id, _ = payload
        self.kademlia.recv_find_node(node, big_endian_to_int(node_id))

    def send_ping(self, node: kademlia.Node) -> bytes:
        version = rlp.sedes.big_endian_int.serialize(PROTO_VERSION)
        payload = [version, self.address.to_endpoint(), node.address.to_endpoint()]
        message = _pack(CMD_PING.id, payload, self.privkey)
        self.send(node, message)
        # Return the msg hash, which is used as a token to identify pongs.
        token = message[:MAC_SIZE]
        self.logger.debug('>>> ping %s (token == %s)', node, encode_hex(token))
        return token

    def send_find_node(self, node: kademlia.Node, target_node_id: int) -> None:
        target_node_id = int_to_big_endian(
            target_node_id).rjust(kademlia.k_pubkey_size // 8, b'\0')
        self.logger.debug('>>> find_node to %s', node)
        message = _pack(CMD_FIND_NODE.id, [target_node_id], self.privkey)
        self.send(node, message)

    def send_pong(self, node: kademlia.Node, token: AnyStr) -> None:
        self.logger.debug('>>> pong %s', node)
        payload = [node.address.to_endpoint(), token]
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
            self.logger.debug('>>> neighbours to %s: %s',
                              node, neighbours[i:i + max_neighbours])
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
    cmd_id = to_bytes(cmd_id)
    expiration = rlp.sedes.big_endian_int.serialize(int(time.time() + EXPIRATION))
    encoded_data = cmd_id + rlp.encode(payload + [expiration])
    signature = privkey.sign_msg(encoded_data)
    message_hash = keccak(signature.to_bytes() + encoded_data)
    return message_hash + signature.to_bytes() + encoded_data


def _unpack(message: AnyStr) -> Tuple[datatypes.PublicKey, int, List[Any], AnyStr]:
    """Unpack a UDP message received from a remote node.

    Returns the public key used to sign the message, the cmd ID, payload and hash.
    """
    message_hash = message[:MAC_SIZE]
    if message_hash != keccak(message[MAC_SIZE:]):
        raise WrongMAC("Wrong msg mac")
    signature = keys.Signature(message[MAC_SIZE:HEAD_SIZE])
    signed_data = message[HEAD_SIZE:]
    remote_pubkey = signature.recover_public_key_from_msg(signed_data)
    cmd_id = safe_ord(message[HEAD_SIZE])
    cmd = CMD_ID_MAP[cmd_id]
    payload = rlp.decode(message[HEAD_SIZE + 1:], strict=False)
    # Ignore excessive list elements as required by EIP-8.
    payload = payload[:cmd.elem_count]
    return remote_pubkey, cmd_id, payload, message_hash


def _test():
    import signal
    from p2p import constants
    from p2p import ecies
    from p2p.exceptions import OperationCancelled

    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

    loop = asyncio.get_event_loop()
    loop.set_debug(True)

    listen_host = '0.0.0.0'
    # Listen on a port other than 30303 in case we want to test against a local geth instance
    # running on that port.
    listen_port = 30301
    privkey = ecies.generate_privkey()
    addr = kademlia.Address(listen_host, listen_port, listen_port)
    discovery = DiscoveryProtocol(privkey, addr, constants.MAINNET_BOOTNODES)
    # local_bootnodes = [
    #     'enode://0x3a514176466fa815ed481ffad09110a2d344f6c9b78c1d14afc351c3a51be33d8072e77939dc03ba44790779b7a1025baf3003f6732430e20cd9b76d953391b3@127.0.0.1:30303']  # noqa: E501
    # discovery = DiscoveryProtocol(privkey, addr, local_bootnodes)
    loop.run_until_complete(discovery.listen(loop))

    async def run():
        try:
            await discovery.bootstrap()
            while True:
                await discovery.lookup_random(CancelToken("Unused"))
        except OperationCancelled:
            # Give all tasks started by DiscoveryProtocol a chance to stop.
            await asyncio.sleep(2)

    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, discovery.stop)

    loop.run_until_complete(run())
    loop.close()


if __name__ == "__main__":
    _test()
