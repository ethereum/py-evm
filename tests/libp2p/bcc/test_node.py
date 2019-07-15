import pytest

from multiaddr import (
    Multiaddr,
)


@pytest.mark.parametrize(
    "num_nodes",
    (
        1,
    )
)
@pytest.mark.asyncio
async def test_node(nodes):
    node = nodes[0]
    expected_addrs = [node.listen_maddr.encapsulate(Multiaddr(f"/p2p/{node.peer_id}"))]
    assert node.host.get_addrs() == expected_addrs


@pytest.mark.parametrize(
    "num_nodes",
    (
        3,
    )
)
@pytest.mark.asyncio
async def test_node_dial_peer(nodes):
    # Test: 0 <-> 1
    await nodes[0].dial_peer(
        nodes[1].listen_ip,
        nodes[1].listen_port,
        nodes[1].peer_id,
    )
    assert nodes[0].peer_id in nodes[1].host.get_network().connections
    assert nodes[1].peer_id in nodes[0].host.get_network().connections
    # Test: Reuse the old connection when connecting again
    original_conn = nodes[1].host.get_network().connections[nodes[0].peer_id]
    await nodes[0].dial_peer(
        nodes[1].listen_ip,
        nodes[1].listen_port,
        nodes[1].peer_id,
    )
    assert nodes[1].host.get_network().connections[nodes[0].peer_id] is original_conn
    # Test: 0 <-> 1 <-> 2
    await nodes[2].dial_peer(
        nodes[1].listen_ip,
        nodes[1].listen_port,
        nodes[1].peer_id,
    )
    assert nodes[1].peer_id in nodes[2].host.get_network().connections
    assert nodes[2].peer_id in nodes[1].host.get_network().connections
    assert len(nodes[1].host.get_network().connections) == 2
