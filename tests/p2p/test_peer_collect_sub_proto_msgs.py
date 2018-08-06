import asyncio
import logging

import pytest

from trinity.protocol.eth.peer import ETHPeer
from trinity.protocol.eth.commands import GetBlockHeaders, GetNodeData
from trinity.protocol.eth.requests import HeaderRequest

from tests.trinity.core.peer_helpers import (
    get_directly_linked_peers,
)


logger = logging.getLogger('testing.p2p.PeerSubscriber')


@pytest.mark.asyncio
async def test_peer_subscriber_filters_messages(request, event_loop):
    peer, remote = await get_directly_linked_peers(
        request,
        event_loop,
        peer1_class=ETHPeer,
        peer2_class=ETHPeer,
    )
    await peer.events.started.wait()

    with peer.collect_sub_proto_messages() as collector:
        assert collector in peer._subscribers
        remote.sub_proto.send_get_node_data([b'\x00' * 32])
        remote.sub_proto.send_get_block_headers(HeaderRequest(0, 1, 0, False))
        remote.sub_proto.send_get_node_data([b'\x00' * 32])
        remote.sub_proto.send_get_block_headers(HeaderRequest(1, 1, 0, False))
        remote.sub_proto.send_get_node_data([b'\x00' * 32])
        await asyncio.sleep(0.01)

    assert collector not in peer._subscribers

    # yield to let remote and peer transmit.

    all_messages = collector.get_messages()
    assert len(all_messages) == 5

    assert isinstance(all_messages[0][1], GetNodeData)
    assert isinstance(all_messages[1][1], GetBlockHeaders)
    assert isinstance(all_messages[2][1], GetNodeData)
    assert isinstance(all_messages[3][1], GetBlockHeaders)
    assert isinstance(all_messages[4][1], GetNodeData)

    # make sure it isn't still collecting
    remote.sub_proto.send_get_block_headers(HeaderRequest(1, 1, 0, False))

    await asyncio.sleep(0.01)

    assert len(collector.get_messages()) == 0
