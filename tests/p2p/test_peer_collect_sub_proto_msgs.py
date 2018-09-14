import asyncio
import logging

import pytest

from p2p.tools.paragon import BroadcastData, GetSum
from p2p.tools.paragon.helpers import (
    get_directly_linked_peers,
)


logger = logging.getLogger('testing.p2p.PeerSubscriber')


@pytest.mark.asyncio
async def test_peer_subscriber_filters_messages(request, event_loop):
    peer, remote = await get_directly_linked_peers(request, event_loop)

    with peer.collect_sub_proto_messages() as collector:
        assert collector in peer._subscribers
        remote.sub_proto.send_broadcast_data(b'broadcast-a')
        remote.sub_proto.send_broadcast_data(b'broadcast-b')
        remote.sub_proto.send_get_sum(7, 8)
        remote.sub_proto.send_broadcast_data(b'broadcast-c')
        await asyncio.sleep(0.01)

    assert collector not in peer._subscribers

    # yield to let remote and peer transmit.

    all_messages = collector.get_messages()
    assert len(all_messages) == 4

    assert isinstance(all_messages[0][1], BroadcastData)
    assert isinstance(all_messages[1][1], BroadcastData)
    assert isinstance(all_messages[2][1], GetSum)
    assert isinstance(all_messages[3][1], BroadcastData)

    # make sure it isn't still collecting
    remote.sub_proto.send_broadcast_data(b'broadcast-d')

    await asyncio.sleep(0.01)

    assert len(collector.get_messages()) == 0
