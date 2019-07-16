import asyncio

import pytest

from trinity.protocol.bcc_libp2p.factories import (
    NodeFactory,
)


@pytest.fixture
def num_nodes():
    return 3


@pytest.fixture
async def nodes(num_nodes):
    _nodes = tuple(
        NodeFactory()
        for _ in range(num_nodes)
    )
    for n in _nodes:
        asyncio.ensure_future(n.run())
        await n.events.started.wait()
    yield _nodes
    for n in _nodes:
        await n.close()
        await n.cancel()
