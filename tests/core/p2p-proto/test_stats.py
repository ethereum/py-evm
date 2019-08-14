import asyncio

from eth_utils import to_tuple
from eth.rlp.headers import BlockHeader
from p2p.peer import (
    PeerSubscriber,
)
import pytest

from trinity.protocol.les.commands import GetBlockHeaders

from trinity.tools.factories import ETHPeerPairFactory, LESV2PeerPairFactory


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


@pytest.mark.asyncio
async def test_eth_get_headers_empty_stats():
    async with ETHPeerPairFactory() as (peer, remote):
        stats = peer.requests.get_stats()
        assert all(status == 'None' for status in stats.values())
        assert 'BlockHeaders' in stats.keys()


@pytest.mark.asyncio
async def test_eth_get_headers_stats():
    async with ETHPeerPairFactory() as (peer, remote):
        async def send_headers():
            remote.sub_proto.send_block_headers(mk_header_chain(1))

        for idx in range(1, 5):
            get_headers_task = asyncio.ensure_future(
                peer.requests.get_block_headers(0, 1, 0, False)
            )
            asyncio.ensure_future(send_headers())

            await get_headers_task

            stats = peer.requests.get_stats()

            assert stats['BlockHeaders'].startswith('msgs={0}  items={0}  rtt='.format(idx))
            assert 'timeouts=0' in stats['BlockHeaders']
            assert 'quality=' in stats['BlockHeaders']
            assert 'ips=' in stats['BlockHeaders']


@pytest.mark.asyncio
async def test_les_get_headers_stats():
    async with LESV2PeerPairFactory() as (peer, remote):
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
