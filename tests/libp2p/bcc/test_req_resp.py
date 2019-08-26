import asyncio

import pytest

from trinity.protocol.bcc_libp2p.configs import ResponseCode
from trinity.protocol.bcc_libp2p.exceptions import HandshakeFailure
from trinity.protocol.bcc_libp2p.messages import HelloRequest
from trinity.protocol.bcc_libp2p.node import REQ_RESP_HELLO_SSZ
from trinity.protocol.bcc_libp2p.utils import read_req, write_resp


@pytest.mark.parametrize("num_nodes", (2,))
@pytest.mark.asyncio
async def test_hello_success(nodes_with_chain):
    nodes = nodes_with_chain
    await nodes[0].dial_peer_maddr(nodes[1].listen_maddr_with_peer_id)
    await nodes[0].say_hello(nodes[1].peer_id)
    await asyncio.sleep(0.01)
    assert nodes[1].peer_id in nodes[0].handshaked_peers
    assert nodes[0].peer_id in nodes[1].handshaked_peers


@pytest.mark.parametrize("num_nodes", (2,))
@pytest.mark.asyncio
async def test_hello_failure_invalid_hello_packet(
    nodes_with_chain, monkeypatch, mock_timeout
):
    nodes = nodes_with_chain
    await nodes[0].dial_peer_maddr(nodes[1].listen_maddr_with_peer_id)

    def _make_inconsistent_hello_packet():
        return HelloRequest(
            fork_version=b"\x12\x34\x56\x78"  # version different from another node.
        )

    monkeypatch.setattr(nodes[0], "_make_hello_packet", _make_inconsistent_hello_packet)
    monkeypatch.setattr(nodes[1], "_make_hello_packet", _make_inconsistent_hello_packet)
    # Test: Handshake fails when either side sends invalid hello packets.
    with pytest.raises(HandshakeFailure):
        await nodes[0].say_hello(nodes[1].peer_id)
    await asyncio.sleep(0.01)
    assert nodes[0].peer_id not in nodes[1].handshaked_peers


@pytest.mark.parametrize("num_nodes", (2,))
@pytest.mark.asyncio
async def test_hello_failure_failure_response(nodes_with_chain):
    nodes = nodes_with_chain
    await nodes[0].dial_peer_maddr(nodes[1].listen_maddr_with_peer_id)

    async def fake_handle_hello(stream):
        await read_req(stream, HelloRequest)
        # The overridden `resp_code` can be anything other than `ResponseCode.SUCCESS`
        await write_resp(stream, "error msg", ResponseCode.INVALID_REQUEST)

    # Mock the handler.
    nodes[1].host.set_stream_handler(REQ_RESP_HELLO_SSZ, fake_handle_hello)
    # Test: Handshake fails when the response is not success.
    with pytest.raises(HandshakeFailure):
        await nodes[0].say_hello(nodes[1].peer_id)
    await asyncio.sleep(0.01)
    assert nodes[0].peer_id not in nodes[1].handshaked_peers
