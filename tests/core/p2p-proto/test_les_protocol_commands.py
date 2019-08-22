import asyncio
import pytest

from p2p.peer import MsgBuffer

from trinity.protocol.les.proto import (
    LESProtocol,
)
from trinity.tools.factories import LESV2PeerPairFactory


@pytest.fixture
async def les_peer_and_remote(request, event_loop):
    async with LESV2PeerPairFactory() as (alice, bob):
        yield alice, bob


@pytest.mark.parametrize(
    'request_id, is_request_id_provided',
    (
        (1, True),
        (5, True),
        (1000, True),
        (None, False),
    )
)
@pytest.mark.asyncio
async def test_les_protocol_methods_request_id(
        les_peer_and_remote, request_id, is_request_id_provided):
    # Test ensuring the correctness of the LES Protocol commands
    # irrespective of whether request_id is provided or not.

    # Setting up the peers which are just connected by streams
    peer, remote = les_peer_and_remote
    assert isinstance(peer.sub_proto, LESProtocol)
    assert isinstance(remote.sub_proto, LESProtocol)

    collector = MsgBuffer()
    remote.add_subscriber(collector)

    # Test for get_block_headers
    generated_request_id = peer.sub_proto.send_get_block_headers(
        b'1234', 1, 0, False, request_id=request_id
    )

    # yield to let remote and peer transmit messages.  This can take a
    # small amount of time so we give it a few rounds of the event loop to
    # finish transmitting.
    for _ in range(10):
        await asyncio.sleep(0.01)
        if collector.msg_queue.qsize() >= 1:
            break

    messages = collector.get_messages()
    assert len(messages) == 1
    peer, cmd, msg = messages[0]

    # Asserted that the reply message has the request_id as that which was generated
    assert generated_request_id == msg['request_id']
    # Assert the generated request_id is same as that which was provided
    if is_request_id_provided:
        assert msg['request_id'] == request_id
    else:
        assert msg['request_id'] != request_id
