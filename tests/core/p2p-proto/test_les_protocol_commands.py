import asyncio
import pytest

from trinity.protocol.les.proto import (
    LESProtocol,
    LESProtocolV2,
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

    # setup message collection
    messages = []
    got_message = asyncio.Event()

    async def collect_messages(conn, cmd, msg):
        messages.append((cmd, msg))
        got_message.set()

    peer.connection.add_protocol_handler(LESProtocolV2, collect_messages)

    # Test for get_block_headers
    generated_request_id = remote.sub_proto.send_get_block_headers(
        b'1234', 1, 0, False, request_id=request_id
    )
    await asyncio.wait_for(got_message.wait(), timeout=1)

    assert len(messages) == 1
    cmd, msg = messages[0]

    # Asserted that the reply message has the request_id as that which was generated
    assert generated_request_id == msg['request_id']
    # Assert the generated request_id is same as that which was provided
    if is_request_id_provided:
        assert msg['request_id'] == request_id
    else:
        assert msg['request_id'] != request_id
