import asyncio
import os
import random

import pytest

from eth_utils import (
    keccak,
)

from trinity.tools.factories import ETHPeerPairFactory


@pytest.fixture
async def eth_peer_and_remote():
    async with ETHPeerPairFactory() as (peer, remote):
        yield peer, remote


def mk_node():
    node_length = random.randint(0, 2048)
    node = os.urandom(node_length)
    return node


def mk_node_data(n):
    if n == 0:
        return tuple(), tuple()
    nodes = tuple(set(mk_node() for _ in range(n)))
    node_keys = tuple(keccak(node) for node in nodes)
    return node_keys, nodes


@pytest.mark.parametrize(
    'node_keys,nodes',
    (
        (
            (keccak(b''),),
            (b'',),
        ),
        mk_node_data(1),
        mk_node_data(4),
        mk_node_data(20),
        mk_node_data(128),
        mk_node_data(384),
    )
)
@pytest.mark.asyncio
async def test_eth_peer_get_node_data_round_trip(eth_peer_and_remote, node_keys, nodes):
    peer, remote = eth_peer_and_remote
    node_data = tuple(zip(node_keys, nodes))

    async def send_node_data():
        remote.sub_proto.send_node_data(nodes)

    request = asyncio.ensure_future(peer.requests.get_node_data(node_keys))
    asyncio.ensure_future(send_node_data())
    response = await request

    assert len(response) == len(node_keys)
    assert response == node_data


@pytest.mark.asyncio
async def test_eth_peer_get_headers_round_trip_partial_response(eth_peer_and_remote):
    peer, remote = eth_peer_and_remote

    node_keys, nodes = mk_node_data(32)
    node_data = tuple(zip(node_keys, nodes))

    async def send_responses():
        remote.sub_proto.send_transactions([])
        await asyncio.sleep(0)
        remote.sub_proto.send_node_data(nodes[:10])
        await asyncio.sleep(0)

    asyncio.ensure_future(send_responses())
    response = await peer.requests.get_node_data(node_keys)

    assert len(response) == 10
    assert response[:10] == node_data[:10]


@pytest.mark.asyncio
async def test_eth_peer_get_headers_round_trip_with_noise(eth_peer_and_remote):
    peer, remote = eth_peer_and_remote

    node_keys, nodes = mk_node_data(32)
    node_data = tuple(zip(node_keys, nodes))

    async def send_responses():
        remote.sub_proto.send_transactions([])
        await asyncio.sleep(0)
        remote.sub_proto.send_node_data(nodes)
        await asyncio.sleep(0)

    asyncio.ensure_future(send_responses())
    response = await peer.requests.get_node_data(node_keys)

    assert len(response) == len(nodes)
    assert response == node_data


@pytest.mark.asyncio
async def test_eth_peer_get_headers_round_trip_does_not_match_invalid_response(eth_peer_and_remote):
    peer, remote = eth_peer_and_remote

    node_keys, nodes = mk_node_data(32)
    node_data = tuple(zip(node_keys, nodes))

    wrong_nodes = tuple(set(mk_node() for _ in range(32)).difference(nodes))

    async def send_responses():
        remote.sub_proto.send_node_data(wrong_nodes)
        await asyncio.sleep(0)
        remote.sub_proto.send_transactions([])
        await asyncio.sleep(0)
        remote.sub_proto.send_node_data(nodes)
        await asyncio.sleep(0)

    asyncio.ensure_future(send_responses())
    response = await peer.requests.get_node_data(node_keys)

    assert len(response) == len(nodes)
    assert response == node_data
