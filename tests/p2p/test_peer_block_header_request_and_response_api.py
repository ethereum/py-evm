import asyncio

import pytest

from eth_utils import to_tuple

from eth.rlp.headers import BlockHeader

from p2p.peer import ETHPeer, LESPeer
from peer_helpers import (
    get_directly_linked_peers,
)


@to_tuple
def mk_header_chain(length):
    assert length >= 1
    genesis = BlockHeader(difficulty=100, block_number=0, gas_limit=3000000)
    yield genesis
    parent = genesis
    if length == 1:
        return

    for i in range(length - 1):
        header = BlockHeader(
            difficulty=100,
            block_number=parent.block_number + 1,
            parent_hash=parent.hash,
            gas_limit=3000000,
        )
        yield header
        parent = header


@pytest.fixture
async def eth_peer_and_remote(request, event_loop):
    peer, remote = await get_directly_linked_peers(
        request,
        event_loop,
        peer1_class=ETHPeer,
        peer2_class=ETHPeer,
    )
    return peer, remote


@pytest.fixture
async def les_peer_and_remote(request, event_loop):
    peer, remote = await get_directly_linked_peers(
        request,
        event_loop,
        peer1_class=LESPeer,
        peer2_class=LESPeer,
    )
    return peer, remote


@pytest.mark.parametrize(
    'params,headers',
    (
        ((0, 1, 0, False), mk_header_chain(1)),
        ((0, 10, 0, False), mk_header_chain(10)),
        ((3, 5, 0, False), mk_header_chain(10)[3:8]),
    )
)
@pytest.mark.asyncio
async def test_eth_peer_get_headers_round_trip(eth_peer_and_remote,
                                               params,
                                               headers):
    peer, remote = eth_peer_and_remote

    async def send_headers():
        remote.sub_proto.send_block_headers(headers)
        await asyncio.sleep(0)

    asyncio.ensure_future(send_headers())
    response = await peer.get_block_headers(*params)

    assert len(response) == len(headers)
    for expected, actual in zip(headers, response):
        assert expected == actual


@pytest.mark.parametrize(
    'params,headers',
    (
        ((0, 1, 0, False), mk_header_chain(1)),
        ((0, 10, 0, False), mk_header_chain(10)),
        ((3, 5, 0, False), mk_header_chain(10)[3:8]),
    )
)
@pytest.mark.asyncio
async def test_les_peer_get_headers_round_trip(les_peer_and_remote,
                                               params,
                                               headers):
    peer, remote = les_peer_and_remote
    request_id = 1234

    peer.gen_request_id = lambda: request_id

    async def send_headers():
        remote.sub_proto.send_block_headers(headers, 0, request_id)
        await asyncio.sleep(0)

    asyncio.ensure_future(send_headers())
    response = await peer.get_block_headers(*params)

    assert len(response) == len(headers)
    for expected, actual in zip(headers, response):
        assert expected == actual


@pytest.mark.asyncio
async def test_eth_peer_get_headers_round_trip_with_noise(eth_peer_and_remote):
    peer, remote = eth_peer_and_remote

    headers = mk_header_chain(10)

    async def send_responses():
        remote.sub_proto.send_node_data([b'arst', b'tsra'])
        await asyncio.sleep(0)
        remote.sub_proto.send_block_headers(headers)
        await asyncio.sleep(0)

    asyncio.ensure_future(send_responses())
    response = await peer.get_block_headers(0, 10, 0, False)

    assert len(response) == len(headers)
    for expected, actual in zip(headers, response):
        assert expected == actual


@pytest.mark.asyncio
async def test_eth_peer_get_headers_round_trip_does_not_match_invalid_response(eth_peer_and_remote):
    peer, remote = eth_peer_and_remote

    headers = mk_header_chain(5)

    wrong_headers = mk_header_chain(10)[3:8]

    async def send_responses():
        remote.sub_proto.send_node_data([b'arst', b'tsra'])
        await asyncio.sleep(0)
        remote.sub_proto.send_block_headers(wrong_headers)
        await asyncio.sleep(0)
        remote.sub_proto.send_block_headers(headers)
        await asyncio.sleep(0)

    asyncio.ensure_future(send_responses())
    response = await peer.get_block_headers(0, 5, 0, False)

    assert len(response) == len(headers)
    for expected, actual in zip(headers, response):
        assert expected == actual
