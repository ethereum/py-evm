import asyncio
import logging
import time

import rlp
from rlp.utils import (
    decode_hex,
    is_integer,
    str_to_bytes,
    safe_ord,
)

from evm.ecc import get_ecc_backend
from evm.p2p import kademlia
from evm.utils.secp256k1 import private_key_to_public_key
from evm.utils.keccak import keccak
from evm.utils.numeric import (
    big_endian_to_int,
    int_to_big_endian,
)


logger = logging.getLogger("discovery")

# coincurve_path = 'evm.ecc.backends.coincurve.CoinCurveECCBackend'
ecc = get_ecc_backend()


class DefectiveMessage(Exception):
    pass


class WrongMAC(DefectiveMessage):
    pass


class PacketExpired(DefectiveMessage):
    pass


"""
# Node Discovery Protocol

**Node**: an entity on the network
**Node ID**: 512 bit public key of node

The Node Discovery protocol provides a way to find RLPx nodes
that can be connected to. It uses a Kademlia-like protocol to maintain a
distributed database of the IDs and endpoints of all listening nodes.

Each node keeps a node table as described in the Kademlia paper
[[Maymounkov, Mazières 2002][kad-paper]]. The node table is configured
with a bucket size of 16 (denoted `k` in Kademlia), concurrency of 3
(denoted `α` in Kademlia), and 8 bits per hop (denoted `b` in
Kademlia) for routing. The eviction check interval is 75 milliseconds,
and the idle bucket-refresh interval is
3600 seconds.

In order to maintain a well-formed network, RLPx nodes should try to connect
to an unspecified number of close nodes. To increase resilience against Sybil attacks,
nodes should also connect to randomly chosen, non-close nodes.

Each node runs the UDP-based RPC protocol defined below. The
`FIND_DATA` and `STORE` requests from the Kademlia paper are not part
of the protocol since the Node Discovery Protocol does not provide DHT
functionality.

[kad-paper]: http://www.cs.rice.edu/Conferences/IPTPS02/109.pdf

## Joining the network

When joining the network, fills its node table by perfoming a
recursive Find Node operation with its own ID as the `Target`. The
initial Find Node request is sent to one or more bootstrap nodes.

## RPC Protocol

RLPx nodes that want to accept incoming connections should listen on
the same port number for UDP packets (Node Discovery Protocol) and
TCP connections (RLPx protocol).

All requests time out after are 300ms. Requests are not re-sent.

"""


class DiscoveryProtocol(asyncio.DatagramProtocol):

    """
    ## Packet Data
    All packets contain an `Expiration` date to guard against replay attacks.
    The date should be interpreted as a UNIX timestamp.
    The receiver should discard any packet whose `Expiration` value is in the past.
    """
    transport = None
    version = 4
    expiration = 60  # let messages expire after N secondes
    cmd_id_map = dict(ping=1, pong=2, find_node=3, neighbours=4)
    rev_cmd_id_map = dict((v, k) for k, v in cmd_id_map.items())

    # number of required top-level list elements for each cmd_id.
    # elements beyond this length are trimmed.
    cmd_elem_count_map = dict(ping=4, pong=3, find_node=2, neighbours=2)

    encoders = dict(cmd_id=chr,
                    expiration=rlp.sedes.big_endian_int.serialize)

    decoders = dict(cmd_id=safe_ord,
                    expiration=rlp.sedes.big_endian_int.deserialize)

    def __init__(self, privkey, address, bootstrap_nodes):
        self.privkey = privkey
        self.pubkey = private_key_to_public_key(self.privkey)
        self.address = address
        self.bootstrap_nodes = bootstrap_nodes
        self.this_node = kademlia.Node(self.pubkey, address)
        self.kademlia = kademlia.KademliaProtocol(self.this_node, wire=self)

    def listen(self, loop):
        return loop.create_datagram_endpoint(
            lambda: self, local_addr=(self.address.ip, self.address.udp_port))

    def connection_made(self, transport):
        self.transport = transport

    @asyncio.coroutine
    def bootstrap(self):
        while self.transport is None:
            # FIXME: Instead of sleeping here to wait until connection_made() is called to set
            # .transport we should instead only call it after we know it's been set.
            yield from asyncio.sleep(1)
        logger.debug("boostrapping with {}".format(self.bootstrap_nodes))
        yield from self.kademlia.bootstrap(self.bootstrap_nodes)

    def datagram_received(self, data, addr):
        self.receive(kademlia.Address(ip=addr[0], udp_port=addr[1]), data)

    def error_received(self, exc):
        logger.warn('error received: {}'.format(exc))

    def send(self, node, message):
        assert node.address
        self.transport.sendto(message, (node.address.ip, node.address.udp_port))

    def stop(self):
        logger.info('stopping discovery')
        self.transport.close()

    def receive(self, address, message):
        try:
            remote_pubkey, cmd_id, payload, mdc = self.unpack(message)
            # Note: as of discovery version 4, expiration is the last element for all
            # packets. This might not be the case for a later version, but just popping
            # the last element is good enough for now.
            expiration = self.decoders['expiration'](payload.pop())
            if time.time() > expiration:
                raise PacketExpired()
        except DefectiveMessage as e:
            logger.info('error unpacking message: {}'.format(e))
            return
        cmd = getattr(self, 'recv_' + self.rev_cmd_id_map[cmd_id])
        node = kademlia.Node(remote_pubkey, address)
        cmd(node, payload, mdc)

    # TODO: Try to extract this into a standalone function.
    def pack(self, cmd_id, payload):
        """
        UDP packets are structured as follows:

        hash || signature || packet-type || packet-data
        packet-type: single byte < 2**7 // valid values are [1,4]
        packet-data: RLP encoded list. Packet properties are serialized in the order in
                    which they're defined. See packet-data below.

        Offset  |
        0       | MDC       | Ensures integrity of packet,
        65      | signature | Ensures authenticity of sender, `SIGN(sender-privkey, MDC)`
        97      | type      | Single byte in range [1, 4] that determines the structure of Data
        98      | data      | RLP encoded, see section Packet Data

        The packets are signed and authenticated. The sender's Node ID is determined by
        recovering the public key from the signature.

            sender-pubkey = ECRECOVER(Signature)

        The integrity of the packet can then be verified by computing the
        expected MDC of the packet as:

            MDC = SHA3(sender-pubkey || type || data)

        As an optimization, implementations may look up the public key by
        the UDP sending address and compute MDC before recovering the sender ID.
        If the MDC values do not match, the packet can be dropped.
        """
        assert cmd_id in self.cmd_id_map.values()
        assert isinstance(payload, list)

        cmd_id = str_to_bytes(self.encoders['cmd_id'](cmd_id))
        expiration = self.encoders['expiration'](int(time.time() + self.expiration))
        encoded_data = cmd_id + rlp.encode(payload + [expiration])
        signature = ecc.ecdsa_sign(encoded_data, self.privkey)
        assert len(signature) == 65
        mdc = keccak(signature + encoded_data)
        assert len(mdc) == 32
        return mdc + signature + encoded_data

    # TODO: Try to extract this into a standalone function.
    def unpack(self, message):
        """
        macSize  = 256 / 8 = 32
        sigSize  = 520 / 8 = 65
        headSize = macSize + sigSize = 97
        hash, sig, sigdata := buf[:macSize], buf[macSize:headSize], buf[headSize:]
        shouldhash := keccak(buf[macSize:])
        """
        mdc = message[:32]
        if mdc != keccak(message[32:]):
            logger.error('packet with wrong mdc')
            raise WrongMAC()
        signature = message[32:97]
        signed_data = message[97:]
        remote_pubkey = ecc.ecdsa_recover(signed_data, signature)
        assert len(remote_pubkey) == 512 / 8
        cmd_id = self.decoders['cmd_id'](message[97])
        cmd = self.rev_cmd_id_map[cmd_id]
        payload = rlp.decode(message[98:], strict=False)
        assert isinstance(payload, list)
        # ignore excessive list elements as required by EIP-8.
        payload = payload[:self.cmd_elem_count_map.get(cmd, len(payload))]
        return remote_pubkey, cmd_id, payload, mdc

    def recv_pong(self, node, payload, mdc):
        if not len(payload) == 2:
            logger.error('invalid pong payload: {}'.format(payload))
            return
        echoed = payload[1]
        self.kademlia.recv_pong(node, echoed)

    def recv_neighbours(self, node, payload, mdc):
        if not len(payload) == 1:
            logger.error('invalid neighbours payload: {}'.format(payload))
            return
        neighbours = []
        for n in payload[0]:
            nodeid = n.pop()
            address = kademlia.Address.from_endpoint(*n)
            neighbours.append(kademlia.Node(nodeid, address))
        self.kademlia.recv_neighbours(node, neighbours)

    def recv_ping(self, node, payload, mdc):
        if len(payload) != 3:
            logger.error('invalid ping payload: '.format(payload))
            return
        self.kademlia.recv_ping(node, mdc)

    def recv_find_node(self, node, payload, mdc):
        logger.debug('<<< find_node from {}'.format(node))
        assert len(payload[0]) == kademlia.k_pubkey_size / 8
        target = big_endian_to_int(payload[0])
        self.kademlia.recv_find_node(node, target)

    def send_ping(self, node):
        assert isinstance(node, type(self.this_node)) and node != self.this_node
        logger.debug('>>> pinging {}'.format(node))
        version = rlp.sedes.big_endian_int.serialize(self.version)
        payload = [version, self.address.to_endpoint(), node.address.to_endpoint()]
        message = self.pack(self.cmd_id_map['ping'], payload)
        self.send(node, message)
        return message[:32]  # return the MDC to identify pongs

    def send_find_node(self, node, target_node_id):
        assert is_integer(target_node_id)
        target_node_id = int_to_big_endian(
            target_node_id).rjust(kademlia.k_pubkey_size // 8, b'\0')
        assert len(target_node_id) == kademlia.k_pubkey_size // 8
        logger.debug('>>> find_node to {}'.format(node))
        message = self.pack(self.cmd_id_map['find_node'], [target_node_id])
        self.send(node, message)

    def send_pong(self, node, token):
        logger.debug('>>> ponging {}'.format(node))
        payload = [node.address.to_endpoint(), token]
        assert len(payload[0][0]) in (4, 16), payload
        message = self.pack(self.cmd_id_map['pong'], payload)
        self.send(node, message)

    def send_neighbours(self, node, neighbours):
        nodes = []
        neighbours = sorted(neighbours)
        for n in neighbours:
            l = n.address.to_endpoint() + [n.pubkey]
            nodes.append(l)
        logger.debug('>>> neighbours to {}: {}'.format(node, neighbours))
        # FIXME: don't brake udp packet size / chunk message / also when receiving
        message = self.pack(self.cmd_id_map['neighbours'], [nodes[:12]])  # FIXME
        self.send(node, message)


if __name__ == "__main__":
    @asyncio.coroutine
    def show_tasks():
        while True:
            tasks = []
            for task in asyncio.Task.all_tasks():
                if task._coro.__name__ != "show_tasks":
                    tasks.append(task._coro.__name__)
            if tasks:
                logger.debug("Active tasks: {}".format(tasks))
            yield from asyncio.sleep(3)

    config = {
        'privkey_hex': '65462b0520ef7d3df61b9992ed3bea0c56ead753be7c8b3614e0ce01e4cac41b',
        'listen_host': '0.0.0.0',
        'listen_port': 30303,
        'p2p_listen_port': 30303,
        'bootstrap_nodes': [
            # Local geth bootnodes
            # b'enode://3a514176466fa815ed481ffad09110a2d344f6c9b78c1d14afc351c3a51be33d8072e77939dc03ba44790779b7a1025baf3003f6732430e20cd9b76d953391b3@127.0.0.1:30301',  # noqa: E501
            # Testnet bootnodes
            # b'enode://6ce05930c72abc632c58e2e4324f7c7ea478cec0ed4fa2528982cf34483094e9cbc9216e7aa349691242576d552a2a56aaeae426c5303ded677ce455ba1acd9d@13.84.180.240:30303',  # noqa: E501
            # b'enode://20c9ad97c081d63397d7b685a412227a40e23c8bdc6688c6f37e97cfbc22d2b4d1db1510d8f61e6a8866ad7f0e17c02b14182d37ea7c3c8b9c2683aeb6b733a1@52.169.14.227:30303',  # noqa: E501
            # Mainnet bootnodes
            # b'enode://a979fb575495b8d6db44f750317d0f4622bf4c2aa3365d6af7c284339968eef29b69ad0dce72a4d8db5ebb4968de0e3bec910127f134779fbcb0cb6d3331163c@52.16.188.185:30303',  # noqa: E501
            # b'enode://3f1d12044546b76342d59d4a05532c14b85aa669704bfe1f864fe079415aa2c02d743e03218e57a33fb94523adb54032871a6c51b2cc5514cb7c7e35b3ed0a99@13.93.211.84:30303',  # noqa: E501
            b'enode://78de8a0916848093c73790ead81d1928bec737d565119932b98c6b100d944b7a95e94f847f689fc723399d2e31129d182f7ef3863f2b4c820abbf3ab2722344d@191.235.84.50:30303',  # noqa: E501
            b'enode://158f8aab45f6d19c6cbf4a089c2670541a8da11978a2f90dbf6a502a4a3bab80d288afdbeb7ec0ef6d92de563767f3b1ea9e8e334ca711e9f8e2df5a0385e8e6@13.75.154.138:30303',  # noqa: E501
            b'enode://1118980bf48b0a3640bdba04e0fe78b1add18e1cd99bf22d53daac1fd9972ad650df52176e7c7d89d1114cfef2bc23a2959aa54998a46afcf7d91809f0855082@52.74.57.123:30303',   # noqa: E501
        ],
    }

    import logging
    logging.basicConfig(level=logging.DEBUG)

    loop = asyncio.get_event_loop()
    loop.set_debug(True)

    privkey = decode_hex(config['privkey_hex'])
    addr = kademlia.Address(config['listen_host'], config['listen_port'], config['p2p_listen_port'])
    bootstrap_nodes = [kademlia.Node.from_uri(x) for x in config['bootstrap_nodes']]
    discovery = DiscoveryProtocol(privkey, addr, bootstrap_nodes)
    loop.run_until_complete(discovery.listen(loop))

    # There's no need to wait for bootstrap because we run_forever().
    asyncio.ensure_future(discovery.bootstrap())

    # This helps when debugging asyncio issues.
    # task_monitor = asyncio.ensure_future(show_tasks())

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

    # task_monitor.set_result(None)
    discovery.stop()
    # logger.info("Pending tasks at exit: {}".format(asyncio.Task.all_tasks(loop)))
    loop.close()
