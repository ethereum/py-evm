import random

import pytest

from evm.p2p import kademlia
from evm.utils.numeric import int_to_big_endian


def get_wired_protocol():
    this_node = random_node()
    return kademlia.KademliaProtocol(this_node, WireMock(this_node))


def test_protocol_bootstrap():
    proto = get_wired_protocol()
    node1 = random_node()
    node2 = random_node()
    proto.bootstrap([node1, node2])
    assert len(proto.wire.messages) == 2
    msg1, msg2 = proto.wire.messages
    assert msg1 == (node1, 'find_node', proto.routing.this_node, proto.routing.this_node.id)
    assert msg2 == (node2, 'find_node', proto.routing.this_node, proto.routing.this_node.id)


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
        # Change nodeid to something in this bucket.
        node_a = nearest_bucket.nodes[0]
        node_b = random_node(node_a.id + 1)
        assert node_a == table.neighbours(node_b.id)[0]


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


def test_compute_shared_prefix_bits():
    # When we have less than 2 nodes, the depth is k_id_size.
    nodes = [random_node()]
    assert kademlia.compute_shared_prefix_bits(nodes) == kademlia.k_id_size

    # Otherwise the depth is the number of leading bits (in the left-padded binary representation)
    # shared by all node IDs.
    nodes.append(random_node())
    nodes[0].id = int('0b1', 2)
    nodes[1].id = int('0b0', 2)
    assert kademlia.compute_shared_prefix_bits(nodes) == kademlia.k_id_size - 1

    nodes[0].id = int('0b010', 2)
    nodes[1].id = int('0b110', 2)
    assert kademlia.compute_shared_prefix_bits(nodes) == kademlia.k_id_size - 3


def random_pubkey():
    pk = int_to_big_endian(random.getrandbits(kademlia.k_pubkey_size))
    return b'\x00' * (kademlia.k_pubkey_size // 8 - len(pk)) + pk


def random_node(nodeid=None):
    node = kademlia.Node(random_pubkey(), address=None)
    if nodeid is not None:
        node.id = nodeid
    return node


def make_routing_table(num_nodes=1000):
    node = random_node()
    table = kademlia.RoutingTable(node)
    for i in range(num_nodes):
        table.add_node(random_node())
    assert i == num_nodes - 1
    return table


class WireMock():

    messages = []

    def __init__(self, sender):
        self.sender = sender

    def send_ping(self, node):
        echo = hex(random.randint(0, 2**256))[-32:]
        self.messages.append((node, 'ping', self.sender, echo))
        return echo

    def send_pong(self, node, echo):
        self.messages.append((node, 'pong', self.sender, echo))

    def send_find_node(self, node, nodeid):
        self.messages.append((node, 'find_node', self.sender, nodeid))

    def send_neighbours(self, node, neighbours):
        self.messages.append((node, 'neighbours', self.sender, neighbours))
