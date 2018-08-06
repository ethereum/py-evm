import asyncio
import logging

import pytest

from p2p.peer import PeerSubscriber
from p2p.protocol import Command

from trinity.protocol.eth.peer import ETHPeer
from trinity.protocol.eth.commands import GetBlockHeaders
from trinity.protocol.eth.requests import (
    HeaderRequest,
    NodeDataRequest,
)

from tests.trinity.core.peer_helpers import (
    get_directly_linked_peers,
)


logger = logging.getLogger('testing.p2p.PeerSubscriber')


class HeadersSubscriber(PeerSubscriber):
    logger = logger
    msg_queue_maxsize = 10
    subscription_msg_types = {GetBlockHeaders}


class AllSubscriber(PeerSubscriber):
    logger = logger
    msg_queue_maxsize = 10
    subscription_msg_types = {Command}


@pytest.mark.asyncio
async def test_peer_subscriber_filters_messages(request, event_loop):
    peer, remote = await get_directly_linked_peers(
        request,
        event_loop,
        peer1_class=ETHPeer,
        peer2_class=ETHPeer,
    )

    header_subscriber = HeadersSubscriber()
    all_subscriber = AllSubscriber()

    peer.add_subscriber(header_subscriber)
    peer.add_subscriber(all_subscriber)

    remote.sub_proto.send_get_node_data(NodeDataRequest([b'\x00' * 32]))
    remote.sub_proto.send_get_block_headers(HeaderRequest(0, 1, 0, False))
    remote.sub_proto.send_get_node_data(NodeDataRequest([b'\x00' * 32]))
    remote.sub_proto.send_get_block_headers(HeaderRequest(1, 1, 0, False))
    remote.sub_proto.send_get_node_data(NodeDataRequest([b'\x00' * 32]))

    # yeild to let remote and peer transmit.
    await asyncio.sleep(0.01)

    assert header_subscriber.queue_size == 2
    assert all_subscriber.queue_size == 5
