import asyncio
import random
import re

import pytest

import rlp

from eth_utils import decode_hex

from eth_hash.auto import keccak

from eth_keys import keys

from cancel_token import CancelToken

from p2p import constants
from p2p import discovery
from p2p.tools.factories import (
    AddressFactory,
    DiscoveryProtocolFactory,
    NodeFactory,
    PrivateKeyFactory,
)


# Force our tests to fail quickly if they accidentally make network requests.
@pytest.fixture(autouse=True)
def short_timeout(monkeypatch):
    monkeypatch.setattr(constants, 'KADEMLIA_REQUEST_TIMEOUT', 0.05)


@pytest.fixture
def alice():
    return DiscoveryProtocolFactory.from_seed(b'alice')


@pytest.fixture
def bob():
    return DiscoveryProtocolFactory.from_seed(b'bob')


def test_ping_pong(alice, bob):
    # Connect alice's and bob's transports directly so we don't need to deal with the complexities
    # of going over the wire.
    link_transports(alice, bob)
    # Collect all pongs received by alice in a list for later inspection.
    received_pongs = []
    alice.recv_pong_v4 = lambda node, payload, hash_: received_pongs.append((node, payload))

    token = alice.send_ping_v4(bob.this_node)

    assert len(received_pongs) == 1
    node, payload = received_pongs[0]
    assert node.id == bob.this_node.id
    assert token == payload[1]


def _test_find_node_neighbours(alice, bob):
    # Add some nodes to bob's routing table so that it has something to use when replying to
    # alice's find_node.
    for _ in range(constants.KADEMLIA_BUCKET_SIZE * 2):
        bob.update_routing_table(NodeFactory())

    # Connect alice's and bob's transports directly so we don't need to deal with the complexities
    # of going over the wire.
    link_transports(alice, bob)
    # Collect all neighbours packets received by alice in a list for later inspection.
    received_neighbours = []
    alice.recv_neighbours_v4 = lambda node, payload, hash_: received_neighbours.append((node, payload))  # noqa: E501
    # Pretend that bob and alice have already bonded, otherwise bob will ignore alice's find_node.
    bob.update_routing_table(alice.this_node)

    alice.send_find_node_v4(bob.this_node, alice.this_node.id)

    # Bob should have sent two neighbours packets in order to keep the total packet size under the
    # 1280 bytes limit.
    assert len(received_neighbours) == 2
    packet1, packet2 = received_neighbours
    neighbours = []
    for packet in [packet1, packet2]:
        node, payload = packet
        assert node == bob.this_node
        neighbours.extend(discovery._extract_nodes_from_payload(
            node.address, payload[0], bob.logger))
    assert len(neighbours) == constants.KADEMLIA_BUCKET_SIZE


def test_find_node_neighbours_v4(alice, bob):
    _test_find_node_neighbours(alice=alice, bob=bob)


@pytest.mark.asyncio
async def test_protocol_bootstrap():
    node1, node2 = NodeFactory.create_batch(2)
    proto = MockDiscoveryProtocol([node1, node2])

    async def bond(node):
        assert proto.routing.add_node(node) is None
        return True

    # Pretend we bonded successfully with our bootstrap nodes.
    proto.bond = bond

    await proto.bootstrap()

    assert len(proto.messages) == 2
    # We don't care in which order the bootstrap nodes are contacted, nor which node_id was used
    # in the find_node request, so we just assert that we sent find_node msgs to both nodes.
    assert sorted([(node, cmd) for (node, cmd, _) in proto.messages]) == sorted([
        (node1, 'find_node'),
        (node2, 'find_node')])


@pytest.mark.asyncio
@pytest.mark.parametrize('echo', ['echo', b'echo'])
async def test_wait_ping(echo):
    proto = MockDiscoveryProtocol([])
    node = NodeFactory()

    # Schedule a call to proto.recv_ping() simulating a ping from the node we expect.
    recv_ping_coroutine = asyncio.coroutine(lambda: proto.recv_ping_v4(node, echo, b''))
    asyncio.ensure_future(recv_ping_coroutine())

    got_ping = await proto.wait_ping(node)

    assert got_ping
    # Ensure wait_ping() cleaned up after itself.
    assert node not in proto.ping_callbacks

    # If we waited for a ping from a different node, wait_ping() would timeout and thus return
    # false.
    recv_ping_coroutine = asyncio.coroutine(lambda: proto.recv_ping_v4(node, echo, b''))
    asyncio.ensure_future(recv_ping_coroutine())

    node2 = NodeFactory()
    got_ping = await proto.wait_ping(node2)

    assert not got_ping
    assert node2 not in proto.ping_callbacks


@pytest.mark.asyncio
async def test_wait_pong():
    proto = MockDiscoveryProtocol([])
    us = proto.this_node
    node = NodeFactory()

    token = b'token'
    # Schedule a call to proto.recv_pong() simulating a pong from the node we expect.
    pong_msg_payload = [us.address.to_endpoint(), token, discovery._get_msg_expiration()]
    recv_pong_coroutine = asyncio.coroutine(lambda: proto.recv_pong_v4(node, pong_msg_payload, b''))
    asyncio.ensure_future(recv_pong_coroutine())

    got_pong = await proto.wait_pong_v4(node, token)

    assert got_pong
    # Ensure wait_pong() cleaned up after itself.
    pingid = proto._mkpingid(token, node)
    assert pingid not in proto.pong_callbacks

    # If the remote node echoed something different than what we expected, wait_pong() would
    # timeout.
    wrong_token = b"foo"
    pong_msg_payload = [us.address.to_endpoint(), wrong_token, discovery._get_msg_expiration()]
    recv_pong_coroutine = asyncio.coroutine(lambda: proto.recv_pong_v4(node, pong_msg_payload, b''))
    asyncio.ensure_future(recv_pong_coroutine())

    got_pong = await proto.wait_pong_v4(node, token)

    assert not got_pong
    assert pingid not in proto.pong_callbacks


@pytest.mark.asyncio
async def test_wait_neighbours():
    proto = MockDiscoveryProtocol([])
    node = NodeFactory()

    # Schedule a call to proto.recv_neighbours_v4() simulating a neighbours response from the node
    # we expect.
    neighbours = tuple(NodeFactory.create_batch(3))
    neighbours_msg_payload = [
        [n.address.to_endpoint() + [n.pubkey.to_bytes()] for n in neighbours],
        discovery._get_msg_expiration()]
    recv_neighbours_coroutine = asyncio.coroutine(
        lambda: proto.recv_neighbours_v4(node, neighbours_msg_payload, b''))
    asyncio.ensure_future(recv_neighbours_coroutine())

    received_neighbours = await proto.wait_neighbours(node)

    assert neighbours == received_neighbours
    # Ensure wait_neighbours() cleaned up after itself.
    assert node not in proto.neighbours_callbacks

    # If wait_neighbours() times out, we get an empty list of neighbours.
    received_neighbours = await proto.wait_neighbours(node)

    assert received_neighbours == tuple()
    assert node not in proto.neighbours_callbacks


@pytest.mark.asyncio
async def test_bond():
    proto = MockDiscoveryProtocol([])
    node = NodeFactory()

    token = b'token'
    # Do not send pings, instead simply return the pingid we'd expect back together with the pong.
    proto.send_ping_v4 = lambda remote: token

    # Pretend we get a pong from the node we are bonding with.
    proto.wait_pong_v4 = asyncio.coroutine(lambda n, t: t == token and n == node)

    bonded = await proto.bond(node)

    assert bonded

    # If we try to bond with any other nodes we'll timeout and bond() will return False.
    node2 = NodeFactory()
    bonded = await proto.bond(node2)

    assert not bonded


def test_update_routing_table():
    proto = MockDiscoveryProtocol([])
    node = NodeFactory()

    assert proto.update_routing_table(node) is None

    assert node in proto.routing


@pytest.mark.asyncio
async def test_update_routing_table_triggers_bond_if_eviction_candidate():
    proto = MockDiscoveryProtocol([])
    old_node, new_node = NodeFactory.create_batch(2)

    bond_called = False

    def bond(node):
        nonlocal bond_called
        bond_called = True
        assert node == old_node

    proto.bond = asyncio.coroutine(bond)
    # Pretend our routing table failed to add the new node by returning the least recently seen
    # node for an eviction check.
    proto.routing.add_node = lambda n: old_node

    proto.update_routing_table(new_node)

    assert new_node not in proto.routing
    # The update_routing_table() call above will have scheduled a future call to proto.bond() so
    # we need to yield here to give it a chance to run.
    await asyncio.sleep(0.001)
    assert bond_called


def test_get_max_neighbours_per_packet():
    proto = DiscoveryProtocolFactory()
    # This test is just a safeguard against changes that inadvertently modify the behaviour of
    # _get_max_neighbours_per_packet().
    assert proto._get_max_neighbours_per_packet() == 12


def test_discover_v4_message_pack():
    sender, recipient = AddressFactory.create_batch(2)
    version = rlp.sedes.big_endian_int.serialize(discovery.PROTO_VERSION)
    payload = (version, sender.to_endpoint(), recipient.to_endpoint())
    privkey = PrivateKeyFactory()

    message = discovery._pack_v4(discovery.CMD_PING.id, payload, privkey)

    pubkey, cmd_id, payload, _ = discovery._unpack_v4(message)
    assert pubkey == privkey.public_key
    assert cmd_id == discovery.CMD_PING.id
    assert len(payload) == discovery.CMD_PING.elem_count


def test_unpack_eip8_packets():
    # Test our _unpack() function against the sample packets specified in
    # https://github.com/ethereum/EIPs/blob/master/EIPS/eip-8.md
    for cmd, packets in eip8_packets.items():
        for _, packet in packets.items():
            pubkey, cmd_id, payload, _ = discovery._unpack_v4(packet)
            assert pubkey.to_hex() == '0xca634cae0d49acb401d8a4c6b6fe8c55b70d115bf400769cc1400f3258cd31387574077f301b421bc84df7266c44e9e6d569fc56be00812904767bf5ccd1fc7f'  # noqa: E501
            assert cmd.id == cmd_id
            assert cmd.elem_count == len(payload)


def remove_whitespace(s):
    return re.sub(r"\s+", "", s)


eip8_packets = {
    discovery.CMD_PING: dict(
        # ping packet with version 4, additional list elements
        ping1=decode_hex(remove_whitespace("""
        e9614ccfd9fc3e74360018522d30e1419a143407ffcce748de3e22116b7e8dc92ff74788c0b6663a
        aa3d67d641936511c8f8d6ad8698b820a7cf9e1be7155e9a241f556658c55428ec0563514365799a
        4be2be5a685a80971ddcfa80cb422cdd0101ec04cb847f000001820cfa8215a8d790000000000000
        000000000000000000018208ae820d058443b9a3550102""")),

        # ping packet with version 555, additional list elements and additional random data
        ping2=decode_hex(remove_whitespace("""
        577be4349c4dd26768081f58de4c6f375a7a22f3f7adda654d1428637412c3d7fe917cadc56d4e5e
        7ffae1dbe3efffb9849feb71b262de37977e7c7a44e677295680e9e38ab26bee2fcbae207fba3ff3
        d74069a50b902a82c9903ed37cc993c50001f83e82022bd79020010db83c4d001500000000abcdef
        12820cfa8215a8d79020010db885a308d313198a2e037073488208ae82823a8443b9a355c5010203
        040531b9019afde696e582a78fa8d95ea13ce3297d4afb8ba6433e4154caa5ac6431af1b80ba7602
        3fa4090c408f6b4bc3701562c031041d4702971d102c9ab7fa5eed4cd6bab8f7af956f7d565ee191
        7084a95398b6a21eac920fe3dd1345ec0a7ef39367ee69ddf092cbfe5b93e5e568ebc491983c09c7
        6d922dc3""")),
    ),

    discovery.CMD_PONG: dict(
        # pong packet with additional list elements and additional random data
        pong=decode_hex(remove_whitespace("""
        09b2428d83348d27cdf7064ad9024f526cebc19e4958f0fdad87c15eb598dd61d08423e0bf66b206
        9869e1724125f820d851c136684082774f870e614d95a2855d000f05d1648b2d5945470bc187c2d2
        216fbe870f43ed0909009882e176a46b0102f846d79020010db885a308d313198a2e037073488208
        ae82823aa0fbc914b16819237dcd8801d7e53f69e9719adecb3cc0e790c57e91ca4461c9548443b9
        a355c6010203c2040506a0c969a58f6f9095004c0177a6b47f451530cab38966a25cca5cb58f0555
        42124e""")),
    ),

    discovery.CMD_FIND_NODE: dict(
        # findnode packet with additional list elements and additional random data
        findnode=decode_hex(remove_whitespace("""
        c7c44041b9f7c7e41934417ebac9a8e1a4c6298f74553f2fcfdcae6ed6fe53163eb3d2b52e39fe91
        831b8a927bf4fc222c3902202027e5e9eb812195f95d20061ef5cd31d502e47ecb61183f74a504fe
        04c51e73df81f25c4d506b26db4517490103f84eb840ca634cae0d49acb401d8a4c6b6fe8c55b70d
        115bf400769cc1400f3258cd31387574077f301b421bc84df7266c44e9e6d569fc56be0081290476
        7bf5ccd1fc7f8443b9a35582999983999999280dc62cc8255c73471e0a61da0c89acdc0e035e260a
        dd7fc0c04ad9ebf3919644c91cb247affc82b69bd2ca235c71eab8e49737c937a2c396""")),
    ),

    discovery.CMD_NEIGHBOURS: dict(
        # neighbours packet with additional list elements and additional random data
        neighbours=decode_hex(remove_whitespace("""
        c679fc8fe0b8b12f06577f2e802d34f6fa257e6137a995f6f4cbfc9ee50ed3710faf6e66f932c4c8
        d81d64343f429651328758b47d3dbc02c4042f0fff6946a50f4a49037a72bb550f3a7872363a83e1
        b9ee6469856c24eb4ef80b7535bcf99c0004f9015bf90150f84d846321163782115c82115db84031
        55e1427f85f10a5c9a7755877748041af1bcd8d474ec065eb33df57a97babf54bfd2103575fa8291
        15d224c523596b401065a97f74010610fce76382c0bf32f84984010203040101b840312c55512422
        cf9b8a4097e9a6ad79402e87a15ae909a4bfefa22398f03d20951933beea1e4dfa6f968212385e82
        9f04c2d314fc2d4e255e0d3bc08792b069dbf8599020010db83c4d001500000000abcdef12820d05
        820d05b84038643200b172dcfef857492156971f0e6aa2c538d8b74010f8e140811d53b98c765dd2
        d96126051913f44582e8c199ad7c6d6819e9a56483f637feaac9448aacf8599020010db885a308d3
        13198a2e037073488203e78203e8b8408dcab8618c3253b558d459da53bd8fa68935a719aff8b811
        197101a4b2b47dd2d47295286fc00cc081bb542d760717d1bdd6bec2c37cd72eca367d6dd3b9df73
        8443b9a355010203b525a138aa34383fec3d2719a0""")),
    ),
}


def link_transports(proto1, proto2):
    # Link both protocol's transports directly by having one's sendto() call the other's
    # datagram_received().
    proto1.transport = type(
        "mock-transport",
        (object,),
        {"sendto": lambda msg, addr: proto2.datagram_received(msg, addr)},
    )
    proto2.transport = type(
        "mock-transport",
        (object,),
        {"sendto": lambda msg, addr: proto1.datagram_received(msg, addr)},
    )


class MockHandler:
    called = False

    def __call__(self, node, payload, msg_hash, raw_msg):
        self.called = True


class MockDiscoveryProtocol(discovery.DiscoveryProtocol):
    def __init__(self, bootnodes):
        privkey = keys.PrivateKey(keccak(b"seed"))
        self.messages = []
        super().__init__(privkey, AddressFactory(), bootnodes, CancelToken("discovery-test"))

    def send_ping_v4(self, node):
        echo = hex(random.randint(0, 2**256))[-32:]
        self.messages.append((node, 'ping', echo))
        return echo

    def send_pong_v4(self, node, echo):
        self.messages.append((node, 'pong', echo))

    def send_find_node_v4(self, node, nodeid):
        self.messages.append((node, 'find_node', nodeid))

    def send_neighbours_v4(self, node, neighbours):
        self.messages.append((node, 'neighbours', neighbours))
