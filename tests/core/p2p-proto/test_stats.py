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
        return msg.command.payload.request_id


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
        stats = peer.eth_api.get_extra_stats()
        assert all('None' in line for line in stats)
        assert any('BlockHeader' in line for line in stats)


@pytest.mark.asyncio
async def test_eth_get_headers_stats():
    async with ETHPeerPairFactory() as (peer, remote):
        async def send_headers():
            remote.eth_api.send_block_headers(mk_header_chain(1))

        for idx in range(1, 5):
            get_headers_task = asyncio.ensure_future(
                peer.eth_api.get_block_headers(0, 1, 0, False)
            )
            asyncio.ensure_future(send_headers())

            await get_headers_task

            stats = peer.eth_api.get_extra_stats()

            for line in stats:
                if 'BlockHeaders' in line:
                    assert 'msgs={0}  items={0}  rtt='.format(idx) in line
                    assert 'timeouts=0' in line
                    assert 'quality=' in line
                    assert 'ips=' in line


@pytest.mark.asyncio
async def test_les_get_headers_stats():
    async with LESV2PeerPairFactory() as (peer, remote):
        request_id_monitor = RequestIDMonitor()

        for idx in range(1, 5):
            with request_id_monitor.subscribe_peer(remote):
                get_headers_task = asyncio.ensure_future(
                    peer.les_api.get_block_headers(0, 1, 0, False)
                )
                request_id = await request_id_monitor.next_request_id()

            remote.les_api.send_block_headers(mk_header_chain(1), 0, request_id)

            await get_headers_task

            stats = peer.les_api.get_extra_stats()[0]

            assert 'msgs={0}  items={0}  rtt='.format(idx) in stats
            assert 'timeouts=0' in stats
            assert 'quality=' in stats
            assert 'ips=' in stats
