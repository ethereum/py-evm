import asyncio

import pytest

from trinity.protocol.bcc_libp2p.messages import (
    HelloRequest,
)


@pytest.mark.parametrize(
    "num_nodes",
    (2,),
)
@pytest.mark.asyncio
async def test_hello_success(nodes_with_chain):
    nodes = nodes_with_chain
    await nodes[0].dial_peer_maddr(nodes[1].listen_maddr_with_peer_id)
    await nodes[0].say_hello(nodes[1].peer_id)
    await asyncio.sleep(0.01)
    assert nodes[1].peer_id in nodes[0].handshaked_peers
    assert nodes[0].peer_id in nodes[1].handshaked_peers


# TODO: test_hello_timeout
@pytest.mark.parametrize(
    "num_nodes",
    (2,),
)
@pytest.mark.asyncio
async def test_hello_failure_packet_not_valid(nodes_with_chain, monkeypatch):
    nodes = nodes_with_chain
    await nodes[0].dial_peer_maddr(nodes[1].listen_maddr_with_peer_id)

    def _make_inconsistent_hello_packet():
        return HelloRequest(
            fork_version=b"\x12\x34\x56\x78",  # version different from another node.
        )
    monkeypatch.setattr(nodes[0], "_make_hello_packet", _make_inconsistent_hello_packet)
    await nodes[0].say_hello(nodes[1].peer_id)
    assert nodes[1].peer_id not in nodes[0].handshaked_peers
    assert nodes[0].peer_id not in nodes[1].handshaked_peers


# TODO: test_hello_failure
