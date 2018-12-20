import asyncio

from eth_utils import to_tuple
from eth.rlp.headers import BlockHeader
from p2p.peer import (
    PeerSubscriber,
)
import pytest

from trinity.protocol.les.commands import GetBlockHeaders
from trinity.protocol.les.peer import LESPeer

from tests.trinity.core.peer_helpers import (
    get_directly_linked_peers,
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
    )
    return peer, remote


@pytest.fixture
async def les_peer_and_remote(request, event_loop):
    peer, remote = await get_directly_linked_peers(
        request,
        event_loop,
        alice_peer_class=LESPeer,
    )
    return peer, remote


@pytest.mark.asyncio
async def test_eth_get_headers_empty_stats(eth_peer_and_remote):
    peer, remote = eth_peer_and_remote
    stats = peer.requests.get_stats()
    assert all(status == 'None' for status in stats.values())
    assert 'BlockHeaders' in stats.keys()


@pytest.mark.asyncio
async def test_eth_get_headers_stats(eth_peer_and_remote):
    peer, remote = eth_peer_and_remote

    async def send_headers():
        remote.sub_proto.send_block_headers(mk_header_chain(1))

    for idx in range(1, 5):
        get_headers_task = asyncio.ensure_future(peer.requests.get_block_headers(0, 1, 0, False))
        asyncio.ensure_future(send_headers())

        await get_headers_task

        stats = peer.requests.get_stats()

        assert stats['BlockHeaders'].startswith('msgs={0}  items={0}  rtt='.format(idx))
        assert 'timeouts=0' in stats['BlockHeaders']
        assert 'quality=' in stats['BlockHeaders']
        assert 'ips=' in stats['BlockHeaders']


@pytest.mark.asyncio
async def test_les_get_headers_stats(les_peer_and_remote):
    peer, remote = les_peer_and_remote

    request_id_monitor = RequestIDMonitor()

    for idx in range(1, 5):
        with request_id_monitor.subscribe_peer(remote):
            get_headers_task = asyncio.ensure_future(
                peer.requests.get_block_headers(0, 1, 0, False)
            )
            request_id = await request_id_monitor.next_request_id()

        remote.sub_proto.send_block_headers(mk_header_chain(1), 0, request_id)

        await get_headers_task

        stats = peer.requests.get_stats()

        assert stats['BlockHeaders'].startswith('msgs={0}  items={0}  rtt='.format(idx))
        assert 'timeouts=0' in stats['BlockHeaders']
        assert 'quality=' in stats['BlockHeaders']
        assert 'ips=' in stats['BlockHeaders']
