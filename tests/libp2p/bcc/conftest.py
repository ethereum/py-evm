import asyncio

import pytest

from eth2.beacon.tools.factories import BeaconChainFactory
from trinity.protocol.bcc_libp2p import utils
from trinity.tools.bcc_factories import NodeFactory

MOCK_TIME = 0.01


@pytest.fixture
def mock_timeout(monkeypatch):
    monkeypatch.setattr(utils, "TTFB_TIMEOUT", MOCK_TIME)
    monkeypatch.setattr(utils, "RESP_TIMEOUT", MOCK_TIME * 2)


@pytest.fixture
def num_nodes():
    return 3


@pytest.fixture
async def nodes(num_nodes):
    async for _nodes in make_nodes(num_nodes, None):
        yield _nodes


@pytest.fixture
async def nodes_with_chain(num_nodes):
    chains = tuple([BeaconChainFactory() for _ in range(num_nodes)])
    async for _nodes in make_nodes(num_nodes, chains):
        yield _nodes


async def make_nodes(num_nodes, chains=None):
    if chains is None:
        _nodes = NodeFactory.create_batch(num_nodes)
    else:
        assert num_nodes == len(chains)
        _nodes = tuple(NodeFactory(chain=chain) for chain in chains)
    for n in _nodes:
        asyncio.ensure_future(n.run())
        await n.events.started.wait()
    try:
        yield _nodes
    finally:
        for n in _nodes:
            await n.close()
            await n.cancel()
