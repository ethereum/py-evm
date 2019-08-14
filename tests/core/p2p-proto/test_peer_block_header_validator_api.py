import asyncio

from eth_utils import to_tuple
from eth.rlp.headers import BlockHeader
from p2p.peer import (
    PeerSubscriber,
)
import pytest

from trinity.protocol.les.commands import GetBlockHeaders

from trinity.tools.factories import (
    ETHPeerPairFactory,
    LESV1PeerPairFactory,
    LESV2PeerPairFactory,
)


class RequestIDMonitor(PeerSubscriber):
    subscription_msg_types = {GetBlockHeaders}
    msg_queue_maxsize = 100

    async def next_request_id(self):
        msg = await self.msg_queue.get()
        return msg.payload['request_id']


@to_tuple
def mk_header_chain(length):
    assert length >= 1
    genesis = BlockHeader(difficulty=100, block_number=0, gas_limit=3000000)
    yield genesis
    parent = genesis
    if length == 1:
        return

    for _ in range(length - 1):
        header = BlockHeader(
            difficulty=100,
            block_number=parent.block_number + 1,
            parent_hash=parent.hash,
            gas_limit=3000000,
        )
        yield header
        parent = header


@pytest.fixture
async def eth_peer_and_remote():
    async with ETHPeerPairFactory() as (peer, remote):
        yield peer, remote


@pytest.fixture(params=(LESV1PeerPairFactory, LESV2PeerPairFactory))
async def les_peer_and_remote(request):
    factory = request.param
    async with factory() as (peer, remote):
        yield peer, remote


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

    get_headers_task = asyncio.ensure_future(peer.requests.get_block_headers(*params))
    asyncio.ensure_future(send_headers())

    response = await get_headers_task

    assert len(response) == len(headers)
    for expected, actual in zip(headers, response):
        assert expected == actual


@pytest.mark.asyncio
async def test_eth_peer_get_headers_round_trip_concurrent_requests(eth_peer_and_remote):
    peer, remote = eth_peer_and_remote
    headers = mk_header_chain(1)

    async def send_headers():
        await asyncio.sleep(0.01)
        remote.sub_proto.send_block_headers(headers)
        await asyncio.sleep(0.01)
        remote.sub_proto.send_block_headers(headers)
        await asyncio.sleep(0.01)
        remote.sub_proto.send_block_headers(headers)

    params = (0, 1, 0, False)

    tasks = [
        asyncio.ensure_future(peer.requests.get_block_headers(*params)),
        asyncio.ensure_future(peer.requests.get_block_headers(*params)),
        asyncio.ensure_future(peer.requests.get_block_headers(*params)),
    ]
    asyncio.ensure_future(send_headers())
    results = await asyncio.gather(*tasks)

    for response in results:
        assert len(response) == 1
        assert response[0] == headers[0]


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
                                               monkeypatch,
                                               headers):
    peer, remote = les_peer_and_remote

    request_id_monitor = RequestIDMonitor()
    with request_id_monitor.subscribe_peer(remote):
        get_headers_task = asyncio.ensure_future(peer.requests.get_block_headers(*params))
        request_id = await request_id_monitor.next_request_id()

    remote.sub_proto.send_block_headers(headers, 0, request_id)

    response = await get_headers_task

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

    get_headers_task = asyncio.ensure_future(peer.requests.get_block_headers(0, 10, 0, False))
    asyncio.ensure_future(send_responses())

    response = await get_headers_task

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

    get_headers_task = asyncio.ensure_future(peer.requests.get_block_headers(0, 5, 0, False))
    asyncio.ensure_future(send_responses())

    response = await get_headers_task

    assert len(response) == len(headers)
    for expected, actual in zip(headers, response):
        assert expected == actual
