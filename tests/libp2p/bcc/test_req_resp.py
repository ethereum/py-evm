import asyncio

import pytest


@pytest.mark.parametrize(
    "num_nodes",
    (2,),
)
@pytest.mark.asyncio
async def test_hello_success(nodes):
    await nodes[0].dial_peer_maddr(nodes[1].listen_maddr_with_peer_id)
    await nodes[0].say_hello(nodes[1].peer_id)
    await asyncio.sleep(0.01)
    assert nodes[1].peer_id in nodes[0].handshaked_peers
    assert nodes[0].peer_id in nodes[1].handshaked_peers


# TODO: test_hello_timeout

# TODO: test_hello_failure

