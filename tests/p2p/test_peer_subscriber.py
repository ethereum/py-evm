import asyncio
import logging

import pytest

from p2p.peer import PeerSubscriber
from p2p.protocol import Command

from p2p.tools.paragon import GetSum
from p2p.tools.paragon.helpers import get_directly_linked_peers


logger = logging.getLogger('testing.p2p.PeerSubscriber')


class GetSumSubscriber(PeerSubscriber):
    logger = logger
    msg_queue_maxsize = 10
    subscription_msg_types = {GetSum}


class AllSubscriber(PeerSubscriber):
    logger = logger
    msg_queue_maxsize = 10
    subscription_msg_types = {Command}


@pytest.mark.asyncio
async def test_peer_subscriber_filters_messages(request, event_loop):
    peer, remote = await get_directly_linked_peers(request, event_loop)

    get_sum_subscriber = GetSumSubscriber()
    all_subscriber = AllSubscriber()

    peer.add_subscriber(get_sum_subscriber)
    peer.add_subscriber(all_subscriber)

    remote.sub_proto.send_broadcast_data(b'value-a')
    remote.sub_proto.send_broadcast_data(b'value-b')
    remote.sub_proto.send_get_sum(7, 8)
    remote.sub_proto.send_get_sum(1234, 4321)
    remote.sub_proto.send_broadcast_data(b'value-b')

    # yeild to let remote and peer transmit.
    await asyncio.sleep(0.02)

    assert get_sum_subscriber.queue_size == 2
    assert all_subscriber.queue_size == 5
