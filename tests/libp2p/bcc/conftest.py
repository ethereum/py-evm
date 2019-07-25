import asyncio

import pytest

from trinity.tools.factories import (
    NodeFactory,
)


@pytest.fixture
def num_nodes():
    return 3


@pytest.fixture
async def nodes(num_nodes):
    _nodes = NodeFactory.create_batch(num_nodes)
    for n in _nodes:
        asyncio.ensure_future(n.run())
        await n.events.started.wait()
    try:
        yield _nodes
    finally:
        for n in _nodes:
            await n.close()
            await n.cancel()
