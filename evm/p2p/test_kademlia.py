import random

import pytest

from evm.p2p import kademlia
from evm.utils.numeric import int_to_big_endian


def test_routingtable_split_bucket():
    table = kademlia.RoutingTable(random_node())
    assert len(table.buckets) == 1
    bucket = table.buckets[0]
    table.split_bucket(bucket)
    assert len(table.buckets) == 2
    assert bucket not in table.buckets


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
        nearest_bucket = table.buckets_by_id_distance(node.id)[0]
        if not nearest_bucket.nodes:
            continue
        # Change nodeid to something in this bucket.
        node_a = nearest_bucket.nodes[0]
        node_b = random_node(node_a.id + 1)
        assert node_a == table.neighbours(node_b.id)[0]


def test_kbucket_add_node():
    bucket = kademlia.KBucket(0, 100)
    node = random_node()
    assert bucket.add_node(node) is None
    assert bucket.nodes == [node]

    node2 = random_node()
    assert bucket.add_node(node2) is None
    assert bucket.nodes == [node, node2]
    assert bucket.head == node

    assert bucket.add_node(node) is None
    assert bucket.nodes == [node2, node]
    assert bucket.head == node2

    bucket.k = 2
    node3 = random_node()
    assert bucket.add_node(node3) == node2
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
        bucket.add_node(node)
    assert bucket.is_full
    bucket1, bucket2 = bucket.split()
    assert bucket1.start == 0
    assert bucket1.end == 50
    assert bucket2.start == 51
    assert bucket2.end == 100
    assert len(bucket1) == bucket.k / 2
    assert len(bucket2) == bucket.k / 2


def test_kbucket_depth():
    bucket = kademlia.KBucket(0, 100)

    # For buckets with less than 2 nodes, the depth is k_id_size.
    assert bucket.depth == kademlia.k_id_size
    assert bucket.add_node(random_node()) is None
    assert bucket.depth == kademlia.k_id_size

    # Otherwise the depth is the number of leading bits (in the left-padded binary representation)
    # shared by all node IDs.
    assert bucket.add_node(random_node()) is None
    bucket.nodes[0].id = int('0b1', 2)
    bucket.nodes[1].id = int('0b0', 2)
    assert bucket.depth == kademlia.k_id_size - 1

    bucket.nodes[0].id = int('0b010', 2)
    bucket.nodes[1].id = int('0b110', 2)
    assert bucket.depth == kademlia.k_id_size - 3


def random_pubkey():
    pk = int_to_big_endian(random.getrandbits(kademlia.k_pubkey_size))
    return b'\x00' * (kademlia.k_pubkey_size // 8 - len(pk)) + pk


def random_node(nodeid=None):
    node = kademlia.Node(random_pubkey())
    if nodeid is not None:
        node.id = nodeid
    return node
