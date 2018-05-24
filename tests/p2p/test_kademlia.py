import asyncio
import random

import pytest

from eth_keys import keys

from eth_utils import (
    int_to_big_endian,
)

from p2p.cancel_token import CancelToken
from p2p import kademlia


# Force our tests to fail quickly if they accidentally make network requests.
@pytest.fixture(autouse=True)
def short_timeout(monkeypatch):
    monkeypatch.setattr(kademlia, 'k_request_timeout', 0.01)


# Depend on the event_loop fixture here to make sure CancelToken uses the default loop installed
# for the tests. More info in https://github.com/pytest-dev/pytest-asyncio/issues/38
@pytest.fixture
def cancel_token(event_loop):
    return CancelToken("cancel_token_fixture")


@pytest.mark.asyncio
async def test_protocol_bootstrap(cancel_token):
    proto = get_wired_protocol()
    node1, node2 = [random_node(), random_node()]

    async def bond(node, cancel_token):
        assert proto.routing.add_node(node) is None
        return True

    # Pretend we bonded successfully with our bootstrap nodes.
    proto.bond = bond

    await proto.bootstrap([node1, node2], cancel_token)

    assert len(proto.wire.messages) == 2
    # We don't care in which order the bootstrap nodes are contacted, nor which node_id was used
    # in the find_node request, so we just assert that we sent find_node msgs to both nodes.
    assert sorted([(node, cmd) for (node, cmd, _) in proto.wire.messages]) == sorted([
        (node1, 'find_node'),
        (node2, 'find_node')])


@pytest.mark.asyncio
@pytest.mark.parametrize('echo', ['echo', b'echo'])
async def test_wait_ping(echo, cancel_token):
    proto = get_wired_protocol()
    node = random_node()

    # Schedule a call to proto.recv_ping() simulating a ping from the node we expect.
    recv_ping_coroutine = asyncio.coroutine(lambda: proto.recv_ping(node, echo))
    asyncio.ensure_future(recv_ping_coroutine())

    got_ping = await proto.wait_ping(node, cancel_token)

    assert got_ping
    # Ensure wait_ping() cleaned up after itself.
    assert node not in proto.ping_callbacks

    # If we waited for a ping from a different node, wait_ping() would timeout and thus return
    # false.
    recv_ping_coroutine = asyncio.coroutine(lambda: proto.recv_ping(node, echo))
    asyncio.ensure_future(recv_ping_coroutine())

    node2 = random_node()
    got_ping = await proto.wait_ping(node2, cancel_token)

    assert not got_ping
    assert node2 not in proto.ping_callbacks


@pytest.mark.asyncio
async def test_wait_pong(cancel_token):
    proto = get_wired_protocol()
    node = random_node()

    token = b'token'
    # Schedule a call to proto.recv_pong() simulating a pong from the node we expect.
    recv_pong_coroutine = asyncio.coroutine(lambda: proto.recv_pong(node, token))
    asyncio.ensure_future(recv_pong_coroutine())

    got_pong = await proto.wait_pong(node, token, cancel_token)

    assert got_pong
    # Ensure wait_pong() cleaned up after itself.
    pingid = proto._mkpingid(token, node)
    assert pingid not in proto.pong_callbacks

    # If the remote node echoed something different than what we expected, wait_pong() would
    # timeout.
    wrong_token = b"foo"
    recv_pong_coroutine = asyncio.coroutine(lambda: proto.recv_pong(node, wrong_token))
    asyncio.ensure_future(recv_pong_coroutine())

    got_pong = await proto.wait_pong(node, token, cancel_token)

    assert not got_pong
    assert pingid not in proto.pong_callbacks


@pytest.mark.asyncio
async def test_wait_neighbours(cancel_token):
    proto = get_wired_protocol()
    node = random_node()

    # Schedule a call to proto.recv_neighbours() simulating a neighbours response from the node we
    # expect.
    neighbours = (random_node(), random_node(), random_node())
    recv_neighbours_coroutine = asyncio.coroutine(lambda: proto.recv_neighbours(node, neighbours))
    asyncio.ensure_future(recv_neighbours_coroutine())

    received_neighbours = await proto.wait_neighbours(node, cancel_token)

    assert neighbours == received_neighbours
    # Ensure wait_neighbours() cleaned up after itself.
    assert node not in proto.neighbours_callbacks

    # If wait_neighbours() times out, we get an empty list of neighbours.
    received_neighbours = await proto.wait_neighbours(node, cancel_token)

    assert received_neighbours == tuple()
    assert node not in proto.neighbours_callbacks


@pytest.mark.asyncio
async def test_bond(cancel_token):
    proto = get_wired_protocol()
    node = random_node()

    token = b'token'
    # Do not send pings, instead simply return the pingid we'd expect back together with the pong.
    proto.ping = lambda remote: token

    # Pretend we get a pong from the node we are bonding with.
    proto.wait_pong = asyncio.coroutine(lambda n, t, cancel_token: t == token and n == node)

    bonded = await proto.bond(node, cancel_token)

    assert bonded

    # If we try to bond with any other nodes we'll timeout and bond() will return False.
    node2 = random_node()
    bonded = await proto.bond(node2, cancel_token)

    assert not bonded


def test_node_from_uri():
    pubkey = 'a979fb575495b8d6db44f750317d0f4622bf4c2aa3365d6af7c284339968eef29b69ad0dce72a4d8db5ebb4968de0e3bec910127f134779fbcb0cb6d3331163c'  # noqa: E501
    ip = '52.16.188.185'
    port = 30303
    uri = 'enode://%s@%s:%d' % (pubkey, ip, port)
    node = kademlia.Node.from_uri(uri)
    assert node.address.ip == ip
    assert node.address.udp_port == node.address.tcp_port == port
    assert node.pubkey.to_hex() == '0x' + pubkey


def test_update_routing_table():
    proto = get_wired_protocol()
    node = random_node()

    assert proto.update_routing_table(node) is None

    assert node in proto.routing


@pytest.mark.asyncio
async def test_update_routing_table_triggers_bond_if_eviction_candidate():
    proto = get_wired_protocol()
    old_node, new_node = random_node(), random_node()

    bond_called = False

    def bond(node, cancel_token):
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


def test_routingtable_split_bucket():
    table = kademlia.RoutingTable(random_node())
    assert len(table.buckets) == 1
    old_bucket = table.buckets[0]
    table.split_bucket(0)
    assert len(table.buckets) == 2
    assert old_bucket not in table.buckets


def test_routingtable_add_node():
    table = kademlia.RoutingTable(random_node())
    for i in range(table.buckets[0].k):
        # As long as the bucket is not full, the new node is added to the bucket and None is
        # returned.
        assert table.add_node(random_node()) is None
        assert len(table.buckets) == 1
        assert len(table) == i + 1
    assert table.buckets[0].is_full
    # Now that the bucket is full, an add_node() should cause it to be split.
    assert table.add_node(random_node()) is None


def test_routingtable_remove_node():
    table = kademlia.RoutingTable(random_node())
    node1 = random_node()
    assert table.add_node(node1) is None
    assert node1 in table

    table.remove_node(node1)

    assert node1 not in table


def test_routingtable_add_node_error():
    table = kademlia.RoutingTable(random_node())
    with pytest.raises(ValueError):
        table.add_node(random_node(kademlia.k_max_node_id + 1))


def test_routingtable_neighbours():
    table = kademlia.RoutingTable(random_node())
    for i in range(1000):
        assert table.add_node(random_node()) is None
        assert i == len(table) - 1

    for i in range(100):
        node = random_node()
        nearest_bucket = table.buckets_by_distance_to(node.id)[0]
        if not nearest_bucket.nodes:
            continue
        # Change nodeid to something that is in this bucket's range.
        node_a = nearest_bucket.nodes[0]
        node_b = random_node(node_a.id + 1)
        assert node_a == table.neighbours(node_b.id)[0]


def test_routingtable_get_random_nodes():
    table = kademlia.RoutingTable(random_node())
    for i in range(100):
        assert table.add_node(random_node()) is None

    nodes = list(table.get_random_nodes(50))
    assert len(nodes) == 50
    assert len(set(nodes)) == 50

    # If we ask for more nodes than what the routing table contains, we'll get only what the
    # routing table contains, without duplicates.
    nodes = list(table.get_random_nodes(200))
    assert len(nodes) == 100
    assert len(set(nodes)) == 100


def test_kbucket_add():
    bucket = kademlia.KBucket(0, 100)
    node = random_node()
    assert bucket.add(node) is None
    assert bucket.nodes == [node]

    node2 = random_node()
    assert bucket.add(node2) is None
    assert bucket.nodes == [node, node2]
    assert bucket.head == node

    assert bucket.add(node) is None
    assert bucket.nodes == [node2, node]
    assert bucket.head == node2

    bucket.k = 2
    node3 = random_node()
    assert bucket.add(node3) == node2
    assert bucket.nodes == [node2, node]
    assert bucket.head == node2


def test_kbucket_split():
    bucket = kademlia.KBucket(0, 100)
    for i in range(1, bucket.k + 1):
        node = random_node()
        # Set the IDs of half the nodes below the midpoint, so when we split we should end up with
        # two buckets containing k/2 nodes.
        if i % 2 == 0:
            node.id = bucket.midpoint + i
        else:
            node.id = bucket.midpoint - i
        bucket.add(node)
    assert bucket.is_full
    bucket1, bucket2 = bucket.split()
    assert bucket1.start == 0
    assert bucket1.end == 50
    assert bucket2.start == 51
    assert bucket2.end == 100
    assert len(bucket1) == bucket.k / 2
    assert len(bucket2) == bucket.k / 2


def test_bucket_ordering():
    first = kademlia.KBucket(0, 50)
    second = kademlia.KBucket(51, 100)
    third = random_node()
    assert first < second
    with pytest.raises(TypeError):
        assert first > third


@pytest.mark.parametrize(
    "bucket_list, node_id",
    (
        (list([]), 5),
        # test for node.id < bucket.end
        (list([kademlia.KBucket(0, 4)]), 5),
        # test for node.id > bucket.start
        (list([kademlia.KBucket(6, 10)]), 5),
        # test multiple buckets that don't contain node.id
        (list(
            [
                kademlia.KBucket(1, 5),
                kademlia.KBucket(6, 49),
                kademlia.KBucket(50, 100),
            ]
        ), 0),
    )
)
def test_binary_get_bucket_for_node_error(bucket_list, node_id):
    node = random_node(nodeid=node_id)
    with pytest.raises(ValueError):
        kademlia.binary_get_bucket_for_node(bucket_list, node)


@pytest.mark.parametrize(
    "bucket_list, node_id, correct_position",
    (
        (list([kademlia.KBucket(0, 100)]), 5, 0),
        (list([kademlia.KBucket(0, 49), kademlia.KBucket(50, 100)]), 5, 0),
        (list(
            [
                kademlia.KBucket(0, 1),
                kademlia.KBucket(2, 5),
                kademlia.KBucket(6, 49),
                kademlia.KBucket(50, 100)
            ]
        ), 5, 1),
    )
)
def test_binary_get_bucket_for_node(bucket_list, node_id, correct_position):
    node = random_node(nodeid=node_id)
    assert kademlia.binary_get_bucket_for_node(bucket_list, node) == bucket_list[correct_position]


def test_compute_shared_prefix_bits():
    # When we have less than 2 nodes, the depth is k_id_size.
    nodes = [random_node()]
    assert kademlia._compute_shared_prefix_bits(nodes) == kademlia.k_id_size

    # Otherwise the depth is the number of leading bits (in the left-padded binary representation)
    # shared by all node IDs.
    nodes.append(random_node())
    nodes[0].id = int('0b1', 2)
    nodes[1].id = int('0b0', 2)
    assert kademlia._compute_shared_prefix_bits(nodes) == kademlia.k_id_size - 1

    nodes[0].id = int('0b010', 2)
    nodes[1].id = int('0b110', 2)
    assert kademlia._compute_shared_prefix_bits(nodes) == kademlia.k_id_size - 3


def get_wired_protocol():
    this_node = random_node()
    return kademlia.KademliaProtocol(this_node, WireMock(this_node))


def random_pubkey():
    pk = int_to_big_endian(random.getrandbits(kademlia.k_pubkey_size))
    return keys.PublicKey(b'\x00' * (kademlia.k_pubkey_size // 8 - len(pk)) + pk)


def random_node(nodeid=None):
    address = kademlia.Address('127.0.0.1', 30303)
    node = kademlia.Node(random_pubkey(), address)
    if nodeid is not None:
        node.id = nodeid
    return node


class WireMock():

    messages = []  # type: ignore
    cancel_token = CancelToken("WireMock")

    def __init__(self, sender):
        self.sender = sender

    def send_ping(self, node):
        echo = hex(random.randint(0, 2**256))[-32:]
        self.messages.append((node, 'ping', echo))
        return echo

    def send_pong(self, node, echo):
        self.messages.append((node, 'pong', echo))

    def send_find_node(self, node, nodeid):
        self.messages.append((node, 'find_node', nodeid))

    def send_neighbours(self, node, neighbours):
        self.messages.append((node, 'neighbours', neighbours))
