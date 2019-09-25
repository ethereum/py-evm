import pytest

from p2p.discv5.routing_table import (
    FlatRoutingTable,
)

from p2p.tools.factories.discovery import (
    NodeIDFactory,
)


@pytest.fixture
def routing_table():
    return FlatRoutingTable()


def test_add(routing_table):
    node_id = NodeIDFactory()
    assert node_id not in routing_table
    routing_table.add(node_id)
    assert node_id in routing_table
    with pytest.raises(ValueError):
        routing_table.add(node_id)


def test_update(routing_table):
    first_node_id = NodeIDFactory()
    second_node_id = NodeIDFactory()

    with pytest.raises(KeyError):
        routing_table.update(first_node_id)
    routing_table.add(first_node_id)
    routing_table.add(second_node_id)

    assert routing_table.get_oldest_entry() == first_node_id
    routing_table.update(first_node_id)
    assert routing_table.get_oldest_entry() == second_node_id


def test_add_or_update(routing_table):
    first_node_id = NodeIDFactory()
    second_node_id = NodeIDFactory()

    routing_table.add_or_update(first_node_id)
    assert first_node_id in routing_table

    routing_table.add(second_node_id)
    assert routing_table.get_oldest_entry() == first_node_id
    routing_table.add_or_update(first_node_id)
    assert routing_table.get_oldest_entry() == second_node_id


def test_remove(routing_table):
    node_id = NodeIDFactory()

    with pytest.raises(KeyError):
        routing_table.remove(node_id)
    routing_table.add(node_id)
    routing_table.remove(node_id)
    assert node_id not in routing_table
