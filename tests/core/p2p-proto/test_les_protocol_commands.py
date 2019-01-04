import asyncio
import pytest

from trinity.protocol.les.peer import (
    LESPeer,
)
from trinity.protocol.les.proto import (
    LESProtocol,
)

from tests.core.peer_helpers import (
    get_directly_linked_peers,
)


@pytest.fixture
async def les_peer_and_remote(request, event_loop):
    peer, remote = await get_directly_linked_peers(
        request,
        event_loop,
        alice_peer_class=LESPeer,
    )
    return peer, remote


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

    # Test for get_block_headers
    with remote.collect_sub_proto_messages() as buffer:
        generated_request_id = peer.sub_proto.send_get_block_headers(
            b'1234', 1, 0, False, request_id=request_id
        )
        await asyncio.sleep(0.1)

    messages = buffer.get_messages()
    assert len(messages) == 1
    peer, cmd, msg = messages[0]

    # Asserted that the reply message has the request_id as that which was generated
    assert generated_request_id == msg['request_id']
    # Assert the generated request_id is same as that which was provided
    if is_request_id_provided:
        assert msg['request_id'] == request_id
    else:
        assert msg['request_id'] != request_id
