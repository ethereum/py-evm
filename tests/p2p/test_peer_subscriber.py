import asyncio
import logging

import pytest

from p2p.peer import PeerSubscriber
from p2p.protocol import Command

from p2p.tools.paragon import GetSum
from p2p.tools.factories import ParagonPeerPairFactory


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
    async with ParagonPeerPairFactory() as (peer, remote):
        get_sum_subscriber = GetSumSubscriber()
        all_subscriber = AllSubscriber()

        peer.add_subscriber(get_sum_subscriber)
        peer.add_subscriber(all_subscriber)

        remote.sub_proto.send_broadcast_data(b'value-a')
        remote.sub_proto.send_broadcast_data(b'value-b')
        remote.sub_proto.send_get_sum(7, 8)
        remote.sub_proto.send_get_sum(1234, 4321)
        remote.sub_proto.send_broadcast_data(b'value-b')

        # Should only be able to get two messages from the `get_sum` subscriber
        for _ in range(2):
            await asyncio.wait_for(get_sum_subscriber.msg_queue.get(), timeout=1)

        # Should be able to get five messages fromt he all subscriber
        for _ in range(5):
            await asyncio.wait_for(all_subscriber.msg_queue.get(), timeout=1)

        # Should now timeout on both queues
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(get_sum_subscriber.msg_queue.get(), timeout=0.01)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(all_subscriber.msg_queue.get(), timeout=0.01)
