import pytest

from p2p import kademlia
from p2p.constants import KADEMLIA_ID_SIZE, KADEMLIA_MAX_NODE_ID
from p2p.kademlia import (
    Address,
    KBucket,
    Node,
    RoutingTable,
    binary_get_bucket_for_node,
    check_relayed_addr,
)
from p2p.tools.factories import (
    NodeFactory,
)


def test_node_from_uri():
    pubkey = 'a979fb575495b8d6db44f750317d0f4622bf4c2aa3365d6af7c284339968eef29b69ad0dce72a4d8db5ebb4968de0e3bec910127f134779fbcb0cb6d3331163c'  # noqa: E501
    ip = '52.16.188.185'
    port = 30303
    uri = 'enode://%s@%s:%d' % (pubkey, ip, port)
    node = Node.from_uri(uri)
    assert node.address.ip == ip
    assert node.address.udp_port == node.address.tcp_port == port
    assert node.pubkey.to_hex() == '0x' + pubkey


def test_routingtable_split_bucket():
    table = RoutingTable(NodeFactory())
    assert len(table.buckets) == 1
    old_bucket = table.buckets[0]
    table.split_bucket(0)
    assert len(table.buckets) == 2
    assert old_bucket not in table.buckets


def test_routingtable_add_node():
    table = RoutingTable(NodeFactory())
    for i in range(table.buckets[0].size):
        # As long as the bucket is not full, the new node is added to the bucket and None is
        # returned.
        assert table.add_node(NodeFactory()) is None
        assert len(table.buckets) == 1
        assert len(table) == i + 1
    assert table.buckets[0].is_full
    # Now that the bucket is full, an add_node() should cause it to be split.
    assert table.add_node(NodeFactory()) is None


def test_routingtable_remove_node():
    table = RoutingTable(NodeFactory())
    node1 = NodeFactory()
    assert table.add_node(node1) is None
    assert node1 in table

    table.remove_node(node1)

    assert node1 not in table


def test_routingtable_add_node_error():
    table = RoutingTable(NodeFactory())
    with pytest.raises(ValueError):
        table.add_node(NodeFactory.with_nodeid(KADEMLIA_MAX_NODE_ID + 1))


def test_routingtable_neighbours():
    table = RoutingTable(NodeFactory())
    for i in range(1000):
        assert table.add_node(NodeFactory()) is None
        assert i == len(table) - 1

    for _ in range(100):
        node = NodeFactory()
        nearest_bucket = table.buckets_by_distance_to(node.id)[0]
        if not nearest_bucket.nodes:
            continue
        # Change nodeid to something that is in this bucket's range.
        node_a = nearest_bucket.nodes[0]
        node_b = NodeFactory.with_nodeid(node_a.id + 1)
        assert node_a == table.neighbours(node_b.id)[0]


def test_routingtable_get_random_nodes():
    table = RoutingTable(NodeFactory())
    for _ in range(100):
        assert table.add_node(NodeFactory()) is None

    nodes = list(table.get_random_nodes(50))
    assert len(nodes) == 50
    assert len(set(nodes)) == 50

    # If we ask for more nodes than what the routing table contains, we'll get only what the
    # routing table contains, without duplicates.
    nodes = list(table.get_random_nodes(200))
    assert len(nodes) == 100
    assert len(set(nodes)) == 100


def test_kbucket_add():
    bucket = KBucket(0, 100)
    node = NodeFactory()
    assert bucket.add(node) is None
    assert bucket.nodes == [node]

    node2 = NodeFactory()
    assert bucket.add(node2) is None
    assert bucket.nodes == [node, node2]
    assert bucket.head == node

    assert bucket.add(node) is None
    assert bucket.nodes == [node2, node]
    assert bucket.head == node2

    bucket.size = 2
    node3 = NodeFactory()
    assert bucket.add(node3) == node2
    assert bucket.nodes == [node2, node]
    assert bucket.head == node2


def test_kbucket_remove():
    bucket = KBucket(0, 100, size=25)

    nodes = NodeFactory.create_batch(bucket.size)
    for node in nodes:
        bucket.add(node)
    assert bucket.nodes == nodes
    assert bucket.replacement_cache == []

    replacement_count = 10
    replacement_nodes = NodeFactory.create_batch(replacement_count)
    for replacement_node in replacement_nodes:
        bucket.add(replacement_node)
    assert bucket.nodes == nodes
    assert bucket.replacement_cache == replacement_nodes

    for node in nodes:
        bucket.remove_node(node)
    assert bucket.nodes == list(reversed(replacement_nodes))
    assert bucket.replacement_cache == []

    for replacement_node in replacement_nodes:
        bucket.remove_node(replacement_node)
    assert bucket.nodes == []
    assert bucket.replacement_cache == []


def test_kbucket_split():
    bucket = KBucket(0, 100)
    for i in range(1, bucket.size + 1):
        node = NodeFactory()
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
    assert len(bucket1) == bucket.size / 2
    assert len(bucket2) == bucket.size / 2


def test_bucket_ordering():
    first = KBucket(0, 50)
    second = KBucket(51, 100)
    third = NodeFactory()
    assert first < second
    with pytest.raises(TypeError):
        assert first > third


@pytest.mark.parametrize(
    "bucket_list, node_id",
    (
        (list([]), 5),
        # test for node.id < bucket.end
        (list([KBucket(0, 4)]), 5),
        # test for node.id > bucket.start
        (list([KBucket(6, 10)]), 5),
        # test multiple buckets that don't contain node.id
        (list(
            [
                KBucket(1, 5),
                KBucket(6, 49),
                KBucket(50, 100),
            ]
        ), 0),
    )
)
def test_binary_get_bucket_for_node_error(bucket_list, node_id):
    node = NodeFactory.with_nodeid(nodeid=node_id)
    with pytest.raises(ValueError):
        binary_get_bucket_for_node(bucket_list, node)


@pytest.mark.parametrize(
    "bucket_list, node_id, correct_position",
    (
        (list([KBucket(0, 100)]), 5, 0),
        (list([KBucket(0, 49), KBucket(50, 100)]), 5, 0),
        (list(
            [
                KBucket(0, 1),
                KBucket(2, 5),
                KBucket(6, 49),
                KBucket(50, 100)
            ]
        ), 5, 1),
    )
)
def test_binary_get_bucket_for_node(bucket_list, node_id, correct_position):
    node = NodeFactory.with_nodeid(nodeid=node_id)
    assert binary_get_bucket_for_node(bucket_list, node) == bucket_list[correct_position]


def test_compute_shared_prefix_bits():
    # When we have less than 2 nodes, the depth is k_id_size.
    nodes = [NodeFactory()]
    assert kademlia._compute_shared_prefix_bits(nodes) == KADEMLIA_ID_SIZE

    # Otherwise the depth is the number of leading bits (in the left-padded binary representation)
    # shared by all node IDs.
    nodes.append(NodeFactory())
    nodes[0].id = int('0b1', 2)
    nodes[1].id = int('0b0', 2)
    assert kademlia._compute_shared_prefix_bits(nodes) == KADEMLIA_ID_SIZE - 1

    nodes[0].id = int('0b010', 2)
    nodes[1].id = int('0b110', 2)
    assert kademlia._compute_shared_prefix_bits(nodes) == KADEMLIA_ID_SIZE - 3


def test_check_relayed_addr():
    public_host = Address('8.8.8.8', 80)
    local_host = Address('127.0.0.1', 80)
    assert check_relayed_addr(local_host, local_host)
    assert not check_relayed_addr(public_host, local_host)

    private = Address('192.168.1.1', 80)
    assert check_relayed_addr(private, private)
    assert not check_relayed_addr(public_host, private)

    reserved = Address('240.0.0.1', 80)
    assert not check_relayed_addr(local_host, reserved)
    assert not check_relayed_addr(public_host, reserved)

    unspecified = Address('0.0.0.0', 80)
    assert not check_relayed_addr(local_host, unspecified)
    assert not check_relayed_addr(public_host, unspecified)
