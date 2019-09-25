import pytest

from p2p.discv5.routing_table import (
    compute_distance,
    compute_log_distance,
    KademliaRoutingTable,
)

from p2p.tools.factories.discovery import (
    NodeIDFactory,
)


@pytest.fixture
def center_node_id():
    return NodeIDFactory()


@pytest.fixture
def bucket_size():
    return 2


@pytest.fixture
def routing_table(center_node_id, bucket_size):
    return KademliaRoutingTable(center_node_id, bucket_size)


@pytest.mark.parametrize(("left_node_id", "right_node_id", "distance"), (
    (b"\x00\x00", b"\x00\x00", 0),
    (b"\x00\x00", b"\x00\xab", 0xab),
    (b"\x00\x00", b"\xff\x00", 0xff00),
    (b"\xff\xff", b"\xff\x00", 0x00ff),
))
def test_distance(left_node_id, right_node_id, distance):
    assert compute_distance(left_node_id, right_node_id) == distance
    assert compute_distance(right_node_id, left_node_id) == distance


@pytest.mark.parametrize(("left_node_id", "right_node_id", "log_distance"), (
    (b"\x00\x00", b"\x00\x01", 0),
    (b"\x00\x00", b"\x00\x02", 1),
    (b"\x00\x00", b"\x00\x03", 1),
    (b"\x00\x00", b"\x00\x04", 2),
    (b"\x00\x00", b"\x00\x08", 3),
    (b"\x00\x00", b"\x00\xff", 7),
    (b"\x00\x00", b"\x01\x00", 8),
    (b"\x00\x00", b"\xf0\x00", 15),
    (b"\x00\x00", b"\xff\xff", 15),
))
def test_log_distance(left_node_id, right_node_id, log_distance):
    assert compute_log_distance(left_node_id, right_node_id) == log_distance
    assert compute_log_distance(right_node_id, left_node_id) == log_distance


def test_add(routing_table, center_node_id):
    assert routing_table.get_nodes_at_log_distance(255) == ()

    node_id_1 = NodeIDFactory.at_log_distance(center_node_id, 255)
    routing_table.update(node_id_1)
    assert routing_table.get_nodes_at_log_distance(255) == (node_id_1,)

    node_id_2 = NodeIDFactory.at_log_distance(center_node_id, 255)
    routing_table.update(node_id_2)
    assert routing_table.get_nodes_at_log_distance(255) == (node_id_2, node_id_1)

    node_id_3 = NodeIDFactory.at_log_distance(center_node_id, 255)
    routing_table.update(node_id_3)
    assert routing_table.get_nodes_at_log_distance(255) == (node_id_2, node_id_1)

    node_id_4 = NodeIDFactory.at_log_distance(center_node_id, 1)
    routing_table.update(node_id_4)
    assert routing_table.get_nodes_at_log_distance(1) == (node_id_4,)


def test_update(routing_table, center_node_id):
    node_id_1 = NodeIDFactory.at_log_distance(center_node_id, 200)
    node_id_2 = NodeIDFactory.at_log_distance(center_node_id, 200)
    routing_table.update(node_id_1)
    routing_table.update(node_id_2)
    assert routing_table.get_nodes_at_log_distance(200) == (node_id_2, node_id_1)
    routing_table.update(node_id_2)
    assert routing_table.get_nodes_at_log_distance(200) == (node_id_2, node_id_1)
    routing_table.update(node_id_1)
    assert routing_table.get_nodes_at_log_distance(200) == (node_id_1, node_id_2)


def test_remove(routing_table, center_node_id):
    node_id_1 = NodeIDFactory.at_log_distance(center_node_id, 200)
    node_id_2 = NodeIDFactory.at_log_distance(center_node_id, 200)
    node_id_3 = NodeIDFactory.at_log_distance(center_node_id, 200)
    node_id_4 = NodeIDFactory.at_log_distance(center_node_id, 200)
    routing_table.update(node_id_1)
    routing_table.update(node_id_2)
    routing_table.update(node_id_3)
    routing_table.update(node_id_4)
    assert routing_table.get_nodes_at_log_distance(200) == (node_id_2, node_id_1)

    routing_table.remove(node_id_4)  # remove from replacement cache, shouldn't appear again
    routing_table.remove(node_id_2)
    assert routing_table.get_nodes_at_log_distance(200) == (node_id_1, node_id_3)
    routing_table.remove(node_id_3)
    assert routing_table.get_nodes_at_log_distance(200) == (node_id_1,)
    routing_table.remove(node_id_1)
    assert routing_table.get_nodes_at_log_distance(200) == ()
    routing_table.remove(node_id_1)  # shouldn't raise


def test_least_recently_updated_distance(routing_table, center_node_id):
    with pytest.raises(ValueError):
        routing_table.get_least_recently_updated_log_distance()

    node_id_1 = NodeIDFactory.at_log_distance(center_node_id, 200)
    routing_table.update(node_id_1)
    assert routing_table.get_least_recently_updated_log_distance() == 200

    node_id_2 = NodeIDFactory.at_log_distance(center_node_id, 100)
    routing_table.update(node_id_2)
    assert routing_table.get_least_recently_updated_log_distance() == 200
    routing_table.update(node_id_1)
    assert routing_table.get_least_recently_updated_log_distance() == 100

    routing_table.remove(node_id_1)
    assert routing_table.get_least_recently_updated_log_distance() == 100

    routing_table.remove(node_id_2)
    with pytest.raises(ValueError):
        routing_table.get_least_recently_updated_log_distance()


def test_is_empty(routing_table):
    assert routing_table.is_empty
    node_id = NodeIDFactory()
    routing_table.update(node_id)
    assert not routing_table.is_empty
    routing_table.remove(node_id)
    assert routing_table.is_empty


def test_iter_around(routing_table, center_node_id):
    reference_node_id = NodeIDFactory.at_log_distance(center_node_id, 100)
    node_ids = tuple(
        NodeIDFactory.at_log_distance(reference_node_id, distance)
        for distance in (1, 2, 100, 200)
    )
    for node_id in node_ids:
        routing_table.update(node_id)

    assert tuple(routing_table.iter_nodes_around(reference_node_id)) == node_ids
    assert tuple(routing_table.iter_nodes_around(node_ids[0])) == node_ids
    assert tuple(routing_table.iter_nodes_around(node_ids[-1])) != node_ids


def test_fill_bucket(routing_table, center_node_id, bucket_size):
    assert not routing_table.get_nodes_at_log_distance(200)
    for _ in range(2 * bucket_size):
        routing_table.update(NodeIDFactory.at_log_distance(center_node_id, 200))
    assert len(routing_table.get_nodes_at_log_distance(200)) == bucket_size


def test_add_center(routing_table, center_node_id):
    with pytest.raises(ValueError):
        routing_table.update(center_node_id)


def test_get_nodes_at_log_distance(routing_table, center_node_id, bucket_size):
    nodes = tuple(NodeIDFactory.at_log_distance(center_node_id, 200) for _ in range(bucket_size))
    farther_nodes = tuple(NodeIDFactory.at_log_distance(center_node_id, 201) for _ in range(5))
    closer_nodes = tuple(NodeIDFactory.at_log_distance(center_node_id, 199) for _ in range(5))
    for node_id in nodes + farther_nodes + closer_nodes:
        routing_table.update(node_id)

    assert set(routing_table.get_nodes_at_log_distance(200)) == set(nodes)
