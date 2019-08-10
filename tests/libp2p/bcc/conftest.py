import asyncio
from math import ceil

import pytest

from eth_utils.toolz import (
    groupby,
)

from trinity.tools.bcc_factories import (
    NodeFactory,
)


@pytest.fixture
def num_nodes():
    return 3


@pytest.fixture
async def nodes(num_nodes):
    async for _nodes in make_nodes(num_nodes, None):
        yield _nodes


@pytest.fixture
async def nodes_with_chain(num_nodes):
    # TODO: Probably it is not suitable to import from `tests`.
    # NOTE: Lazy imports since they are expensive.
    from tests.plugins.eth2.beacon.helpers import (
        bcc_helpers,
        NUM_VALIDATORS,
    )
    from tests.plugins.eth2.beacon.test_validator import (
        get_chain_from_genesis,
    )

    assert num_nodes <= NUM_VALIDATORS
    all_indices = range(NUM_VALIDATORS)
    group_size = ceil(NUM_VALIDATORS / num_nodes)
    distributed_indices = groupby(lambda x: x // group_size, all_indices)

    async def get_chain(indices):
        chain_db = await bcc_helpers.get_chain_db()
        return get_chain_from_genesis(chain_db.db, indices)
    chains = await asyncio.gather(*[
        get_chain(indices)
        for indices in distributed_indices.values()
    ])
    async for _nodes in make_nodes(num_nodes, chains):
        yield _nodes


async def make_nodes(num_nodes, chains=None):
    if chains is None:
        _nodes = NodeFactory.create_batch(num_nodes)
    else:
        assert num_nodes == len(chains)
        _nodes = tuple(
            NodeFactory(chain=chain)
            for chain in chains
        )
    for n in _nodes:
        asyncio.ensure_future(n.run())
        await n.events.started.wait()
    try:
        yield _nodes
    finally:
        for n in _nodes:
            await n.close()
            await n.cancel()
