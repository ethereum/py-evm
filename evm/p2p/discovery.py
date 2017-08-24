import asyncio
import ipaddress
import struct
import time

import rlp
from rlp.utils import (
    decode_hex,
    encode_hex,
    is_integer,
    str_to_bytes,
    safe_ord,
)

from repoze.lru import LRUCache

from evm.p2p import kademlia
from evm.p2p.upnp import add_portmap, remove_portmap
from evm.utils.ecdsa import (
    ecdsa_recover,
    ecdsa_sign,
)
from evm.utils.secp256k1 import private_key_to_public_key
from evm.utils.keccak import keccak
from evm.utils.numeric import (
    big_endian_to_int,
    int_to_big_endian,
)


class DefectiveMessage(Exception):
    pass


class WrongMAC(DefectiveMessage):
    pass


class PacketExpired(DefectiveMessage):
    pass


def int_to_big_endian4(integer):
    ''' 4 bytes big endian integer'''
    return struct.pack('>I', integer)


def enc_port(p):
    return int_to_big_endian4(p)[-2:]


class Address(object):

    def __init__(self, ip, udp_port, tcp_port=0, from_binary=False):
        tcp_port = tcp_port or udp_port
        if from_binary:
            self.udp_port = big_endian_to_int(udp_port)
            self.tcp_port = big_endian_to_int(tcp_port)
        else:
            assert is_integer(udp_port)
            assert is_integer(tcp_port)
            self.udp_port = udp_port
            self.tcp_port = tcp_port
        try:
            self._ip = ipaddress.ip_address(ip)
        except ipaddress.AddressValueError as e:
            log.debug("failed to parse ip", error=e, ip=ip)
            raise e

    @property
    def ip(self):
        return str(self._ip)

    def update(self, addr):
        if not self.tcp_port:
            self.tcp_port = addr.tcp_port

    def __eq__(self, other):
        # addresses equal if they share ip and udp_port
        return (self.ip, self.udp_port) == (other.ip, other.udp_port)

    def __repr__(self):
        return 'Address(%s:%s)' % (self.ip, self.udp_port)

    def to_dict(self):
        return dict(ip=self.ip, udp_port=self.udp_port, tcp_port=self.tcp_port)

    def to_binary(self):
        """
        struct Endpoint
            unsigned address; // BE encoded 32-bit or 128-bit unsigned
                                 (layer3 address; size determins ipv4 vs ipv6)
            unsigned udpPort; // BE encoded 16-bit unsigned
            unsigned tcpPort; // BE encoded 16-bit unsigned        }
        """
        return list((self._ip.packed, enc_port(self.udp_port), enc_port(self.tcp_port)))
    to_endpoint = to_binary

    @classmethod
    def from_binary(cls, ip, udp_port, tcp_port='\x00\x00'):
        return cls(ip, udp_port, tcp_port, from_binary=True)
    from_endpoint = from_binary


class Node(kademlia.Node):

    def __init__(self, pubkey, address=None):
        super(Node, self).__init__(pubkey)
        assert address is None or isinstance(address, Address)
        self.address = address

    @classmethod
    def from_uri(cls, uri):
        ip, port, pubkey = host_port_pubkey_from_uri(uri)
        return cls(pubkey, Address(ip.decode(), int(port)))

    def __repr__(self):
        return '<Node(%s:%s)>' % (encode_hex(self.pubkey[:4]), self.address.ip)


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
    bootstrapped = False
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
        self.this_node = Node(self.pubkey, address)
        self.nodes = LRUCache(2048)   # nodeid->Node,  fixme should be loaded
        self.kademlia = kademlia.KademliaProtocol(self.this_node, wire=self)
        self.nat_upnp = add_portmap(address.udp_port, 'UDP', 'Ethereum DEVP2P Discovery')

    def listen(self, loop):
        return loop.create_datagram_endpoint(
            lambda: self, local_addr=(self.address.ip, self.address.udp_port))

    def connection_made(self, transport):
        self.transport = transport

    def bootstrap(self):
        if self.bootstrapped or len(self.bootstrap_nodes) == 0:
            return
        while self.transport is None:
            yield from asyncio.sleep(1)
        self.bootstrapped = True
        # XXX: geth will not process a find_node packet unless a bond exists between the
        # nodes (introduced in de7af720d6bb10b93d716fb0c6cf3ee0e51dc71a), and to create a
        # node a node must ping the other, so as a quick hack I ping all nodes before
        # starting the bootstrap.
        list(map(self.send_ping, self.bootstrap_nodes))
        self.kademlia.bootstrap(self.bootstrap_nodes)

    def datagram_received(self, data, addr):
        self.receive(Address(ip=addr[0], udp_port=addr[1]), data)

    def error_received(self, exc):
        log.warn('error received', err=exc)

    def send(self, node, message):
        assert node.address
        self.transport.sendto(message, (node.address.ip, node.address.udp_port))

    def stop(self):
        log.info('stopping discovery')
        self.transport.close()
        remove_portmap(self.nat_upnp, self.address.udp_port, 'UDP')

    def get_node(self, nodeid, address=None):
        "return node or create new, update address if supplied"
        assert isinstance(nodeid, bytes)
        assert len(nodeid) == 512 // 8
        assert address or self.nodes.get(nodeid)
        if not self.nodes.get(nodeid):
            self.nodes.put(nodeid, Node(nodeid, address))
        node = self.nodes.get(nodeid)
        if address:
            assert isinstance(address, Address)
            node.address = address
        assert node.address
        return node

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
        signature = ecdsa_sign(encoded_data, self.privkey)
        assert len(signature) == 65
        mdc = keccak(signature + encoded_data)
        assert len(mdc) == 32
        return mdc + signature + encoded_data

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
            log.debug('packet with wrong mcd')
            raise WrongMAC()
        signature = message[32:97]
        assert len(signature) == 65
        signed_data = keccak(message[97:])
        remote_pubkey = ecdsa_recover(signed_data, signature)
        assert len(remote_pubkey) == 512 / 8
        cmd_id = self.decoders['cmd_id'](message[97])
        cmd = self.rev_cmd_id_map[cmd_id]
        payload = rlp.decode(message[98:], strict=False)
        assert isinstance(payload, list)
        # ignore excessive list elements as required by EIP-8.
        payload = payload[:self.cmd_elem_count_map.get(cmd, len(payload))]
        return remote_pubkey, cmd_id, payload, mdc

    def receive(self, address, message):
        assert isinstance(address, Address)
        try:
            remote_pubkey, cmd_id, payload, mdc = self.unpack(message)
            # Note: as of discovery version 4, expiration is the last element for all
            # packets. This might not be the case for a later version, but just popping
            # the last element is good enough for now.
            expiration = self.decoders['expiration'](payload.pop())
            if time.time() > expiration:
                raise PacketExpired()
        except DefectiveMessage:
            return
        cmd = getattr(self, 'recv_' + self.rev_cmd_id_map[cmd_id])
        nodeid = remote_pubkey
        remote = self.get_node(nodeid, address)
        log.debug("Dispatching received message", local=self.this_node, remoteid=remote,
                  cmd=self.rev_cmd_id_map[cmd_id])
        cmd(nodeid, payload, mdc)

    def send_ping(self, node):
        """
        ### Ping (type 0x01)

        Ping packets can be sent and received at any time. The receiver should
        reply with a Pong packet and update the IP/Port of the sender in its
        node table.

        PingNode packet-type: 0x01

        PingNode packet-type: 0x01
        struct PingNode             <= 59 bytes
        {
            h256 version = 0x3;     <= 1
            Endpoint from;          <= 23
            Endpoint to;            <= 23
            unsigned expiration;    <= 9
        };

        struct Endpoint             <= 24 == [17,3,3]
        {
            unsigned address; // BE encoded 32-bit or 128-bit unsigned
                                 (layer3 address; size determins ipv4 vs ipv6)
            unsigned udpPort; // BE encoded 16-bit unsigned
            unsigned tcpPort; // BE encoded 16-bit unsigned
        }
        """
        assert isinstance(node, type(self.this_node)) and node != self.this_node
        log.debug('>>> ping', remoteid=node)
        version = rlp.sedes.big_endian_int.serialize(self.version)
        payload = [version, self.address.to_endpoint(), node.address.to_endpoint()]
        message = self.pack(self.cmd_id_map['ping'], payload)
        self.send(node, message)
        return message[:32]  # return the MDC to identify pongs

    def recv_pong(self, nodeid, payload, mdc):
        if not len(payload) == 2:
            log.error('invalid pong payload', payload=payload)
            return
        assert len(payload[0]) == 3, payload

        # Verify address is valid
        Address.from_endpoint(*payload[0])
        echoed = payload[1]
        if self.nodes.get(nodeid):
            node = self.get_node(nodeid)
            self.kademlia.recv_pong(node, echoed)
        else:
            log.debug('<<< unexpected pong from unkown node')

    def send_find_node(self, node, target_node_id):
        """
        ### Find Node (type 0x03)

        Find Node packets are sent to locate nodes close to a given target ID.
        The receiver should reply with a Neighbors packet containing the `k`
        nodes closest to target that it knows about.

        FindNode packet-type: 0x03
        struct FindNode             <= 76 bytes
        {
            NodeId target; // Id of a node. The responding node will send back nodes closest
                              to the target.
            unsigned expiration;
        };
        """
        assert is_integer(target_node_id)
        target_node_id = int_to_big_endian(
            target_node_id).rjust(kademlia.k_pubkey_size // 8, b'\0')
        assert len(target_node_id) == kademlia.k_pubkey_size // 8
        log.debug('>>> find_node', remoteid=node)
        message = self.pack(self.cmd_id_map['find_node'], [target_node_id])
        self.send(node, message)

    def recv_neighbours(self, nodeid, payload, mdc):
        remote = self.get_node(nodeid)
        assert len(payload) == 1
        neighbours_lst = payload[0]
        assert isinstance(neighbours_lst, list)

        neighbours = []
        for n in neighbours_lst:
            nodeid = n.pop()
            address = Address.from_endpoint(*n)
            node = self.get_node(nodeid, address)
            assert node.address
            neighbours.append(node)

        self.kademlia.recv_neighbours(remote, neighbours)

    # NOTE(gsalgado): Does a light client need to listen/reply to those messages? Need to find out
    def recv_ping(self, nodeid, payload, mdc):
        """
        update ip, port in node table
        Addresses can only be learned by ping messages
        """
        if not len(payload) == 3:
            log.error('invalid ping payload', payload=payload)
            return
        node = self.get_node(nodeid)
        remote_address = Address.from_endpoint(*payload[1])  # from address
        # my_address = Address.from_endpoint(*payload[2])  # my address
        self.get_node(nodeid).address.update(remote_address)
        self.kademlia.recv_ping(node, echo=mdc)

    def send_pong(self, node, token):
        """
        ### Pong (type 0x02)

        Pong is the reply to a Ping packet.

        Pong packet-type: 0x02
        struct Pong                 <= 66 bytes
        {
            Endpoint to;
            h256 echo;
            unsigned expiration;
        };
        """
        log.debug('>>> pong', remoteid=node)
        payload = [node.address.to_endpoint(), token]
        assert len(payload[0][0]) in (4, 16), payload
        message = self.pack(self.cmd_id_map['pong'], payload)
        self.send(node, message)

    def recv_find_node(self, nodeid, payload, mdc):
        node = self.get_node(nodeid)
        log.debug('<<< find_node', remoteid=node)
        assert len(payload[0]) == kademlia.k_pubkey_size / 8
        target = big_endian_to_int(payload[0])
        self.kademlia.recv_find_node(node, target)

    def send_neighbours(self, node, neighbours):
        """
        ### Neighbors (type 0x04)

        Neighbors is the reply to Find Node. It contains up to `k` nodes that
        the sender knows which are closest to the requested `Target`.

        Neighbors packet-type: 0x04
        struct Neighbours           <= 1423
        {
            list nodes: struct Neighbour    <= 88: 1411; 76: 1219
            {
                inline Endpoint endpoint;
                NodeId node;
            };

            unsigned expiration;
        };
        """
        assert isinstance(neighbours, list)
        assert not neighbours or isinstance(neighbours[0], Node)
        nodes = []
        neighbours = sorted(neighbours)
        for n in neighbours:
            l = n.address.to_endpoint() + [n.pubkey]
            nodes.append(l)
        log.debug('>>> neighbours', remoteid=node, count=len(nodes), local=self.this_node,
                  neighbours=neighbours)
        # FIXME: don't brake udp packet size / chunk message / also when receiving
        message = self.pack(self.cmd_id_map['neighbours'], [nodes[:12]])  # FIXME
        self.send(node, message)


def host_port_pubkey_from_uri(uri):
    node_uri_scheme = 'enode://'
    b_node_uri_scheme = str_to_bytes(node_uri_scheme)
    assert uri.startswith(b_node_uri_scheme) and \
        b'@' in uri and b':' in uri, uri
    pubkey_hex, ip_port = uri[len(b_node_uri_scheme):].split(b'@')
    assert len(pubkey_hex) == 2 * 512 // 8
    ip, port = ip_port.split(b':')
    return ip, port, decode_hex(pubkey_hex)


if __name__ == "__main__":
    @asyncio.coroutine
    def show_tasks():
        while True:
            tasks = []
            for task in asyncio.Task.all_tasks():
                if task._coro.__name__ != "show_tasks":
                    tasks.append(task._coro.__name__)
            if tasks:
                log.debug("Active tasks: {}".format(tasks))
            yield from asyncio.sleep(3)

    config = {
        'privkey_hex': '65462b0520ef7d3df61b9992ed3bea0c56ead753be7c8b3614e0ce01e4cac41b',
        # 'privkey_hex': '45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8',
        'listen_host': '0.0.0.0',
        'listen_port': 30303,
        'p2p_listen_port': 30303,
        'bootstrap_nodes': [
            # Local geth bootnodes
            # b'enode://3a514176466fa815ed481ffad09110a2d344f6c9b78c1d14afc351c3a51be33d8072e77939dc03ba44790779b7a1025baf3003f6732430e20cd9b76d953391b3@127.0.0.1:30301',  # noqa: E501
            # Testnet bootnodes
            b'enode://6ce05930c72abc632c58e2e4324f7c7ea478cec0ed4fa2528982cf34483094e9cbc9216e7aa349691242576d552a2a56aaeae426c5303ded677ce455ba1acd9d@13.84.180.240:30303',  # noqa: E501
            # b'enode://20c9ad97c081d63397d7b685a412227a40e23c8bdc6688c6f37e97cfbc22d2b4d1db1510d8f61e6a8866ad7f0e17c02b14182d37ea7c3c8b9c2683aeb6b733a1@52.169.14.227:30303',  # noqa: E501
            # Mainnet bootnodes
            b'enode://a979fb575495b8d6db44f750317d0f4622bf4c2aa3365d6af7c284339968eef29b69ad0dce72a4d8db5ebb4968de0e3bec910127f134779fbcb0cb6d3331163c@52.16.188.185:30303',  # noqa: E501
            # b'enode://3f1d12044546b76342d59d4a05532c14b85aa669704bfe1f864fe079415aa2c02d743e03218e57a33fb94523adb54032871a6c51b2cc5514cb7c7e35b3ed0a99@13.93.211.84:30303',  # noqa: E501
            # b'enode://78de8a0916848093c73790ead81d1928bec737d565119932b98c6b100d944b7a95e94f847f689fc723399d2e31129d182f7ef3863f2b4c820abbf3ab2722344d@191.235.84.50:30303',  # noqa: E501
            # b'enode://158f8aab45f6d19c6cbf4a089c2670541a8da11978a2f90dbf6a502a4a3bab80d288afdbeb7ec0ef6d92de563767f3b1ea9e8e334ca711e9f8e2df5a0385e8e6@13.75.154.138:30303',  # noqa: E501
            # b'enode://1118980bf48b0a3640bdba04e0fe78b1add18e1cd99bf22d53daac1fd9972ad650df52176e7c7d89d1114cfef2bc23a2959aa54998a46afcf7d91809f0855082@52.74.57.123:30303',   # noqa: E501
        ],
    }

    import logging
    logging.basicConfig(level=logging.DEBUG)

    loop = asyncio.get_event_loop()
    loop.set_debug(True)

    from structlog import get_logger
    log = get_logger()

    privkey = decode_hex(config['privkey_hex'])
    addr = Address(config['listen_host'], config['listen_port'], config['p2p_listen_port'])
    bootstrap_nodes = [Node.from_uri(x) for x in config['bootstrap_nodes']]
    discovery = DiscoveryProtocol(privkey, addr, bootstrap_nodes)
    # This will cause DiscoveryProtocol to start listening locally *and* also initiate the
    # discovery bootstrap process (via the connection_made() method).
    loop.run_until_complete(discovery.listen(loop))

    asyncio.ensure_future(discovery.bootstrap())

    # This helps when debugging asyncio issues.
    # task_monitor = asyncio.ensure_future(show_tasks())

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

    # task_monitor.set_result(None)
    discovery.stop()
    # log.info("Pending tasks at exit: {}".format(asyncio.Task.all_tasks(loop)))
    loop.close()
