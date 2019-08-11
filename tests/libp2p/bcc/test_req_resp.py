import asyncio

import pytest

from trinity.protocol.bcc_libp2p import utils
from trinity.protocol.bcc_libp2p.node import (
    REQ_RESP_HELLO_SSZ,
)
from trinity.protocol.bcc_libp2p.configs import (
    ResponseCode,
)
from trinity.protocol.bcc_libp2p.exceptions import (
    HandshakeFailure,
)
from trinity.protocol.bcc_libp2p.messages import (
    HelloRequest,
)


MOCK_TIME = 0.01


@pytest.fixture
def mock_timeout(monkeypatch):
    monkeypatch.setattr(utils, "TTFB_TIMEOUT", MOCK_TIME)
    monkeypatch.setattr(utils, "RESP_TIMEOUT", MOCK_TIME * 2)


def test_resp_code_standard():
    assert ResponseCode.SUCCESS == ResponseCode(0)
    assert ResponseCode.INVALID_REQUEST == ResponseCode(1)
    assert ResponseCode.SERVER_ERROR == ResponseCode(2)


@pytest.mark.parametrize(
    "code_value",
    (
        ResponseCode._standard_codes +
        (ResponseCode._non_standard_codes[0], ResponseCode._non_standard_codes[-1])  # edges
    ),
)
def test_resp_code_valid(code_value):
    code = ResponseCode(code_value)
    assert code_value == code.to_int()
    assert ResponseCode.from_bytes(code.to_bytes()) == code


@pytest.mark.parametrize(
    "code_value",
    (-1, 256, 257,),
)
def test_resp_code_invalid(code_value):
    with pytest.raises(ValueError):
        ResponseCode(code_value)


@pytest.mark.parametrize(
    "code_bytes",
    (b"", b"12",),
)
def test_resp_code_from_bytes_failure(code_bytes):
    with pytest.raises(ValueError):
        ResponseCode.from_bytes(code_bytes)


@pytest.mark.parametrize(
    "num_nodes",
    (2,),
)
@pytest.mark.asyncio
async def test_hello_success(nodes_with_chain):
    nodes = nodes_with_chain
    await nodes[0].dial_peer_maddr(nodes[1].listen_maddr_with_peer_id)
    await nodes[0].say_hello(nodes[1].peer_id)
    await asyncio.sleep(0.01)
    assert nodes[1].peer_id in nodes[0].handshaked_peers
    assert nodes[0].peer_id in nodes[1].handshaked_peers


@pytest.mark.parametrize(
    "num_nodes",
    (2,),
)
@pytest.mark.asyncio
async def test_hello_failure_invalid_hello_packet(nodes_with_chain, monkeypatch, mock_timeout):
    nodes = nodes_with_chain
    await nodes[0].dial_peer_maddr(nodes[1].listen_maddr_with_peer_id)

    def _make_inconsistent_hello_packet():
        return HelloRequest(
            fork_version=b"\x12\x34\x56\x78",  # version different from another node.
        )
    monkeypatch.setattr(nodes[0], "_make_hello_packet", _make_inconsistent_hello_packet)
    monkeypatch.setattr(nodes[1], "_make_hello_packet", _make_inconsistent_hello_packet)
    # Test: Handshake fails when either side sends invalid hello packets.
    with pytest.raises(HandshakeFailure):
        await nodes[0].say_hello(nodes[1].peer_id)
    await asyncio.sleep(0.01)
    assert nodes[0].peer_id not in nodes[1].handshaked_peers


@pytest.mark.parametrize(
    "num_nodes",
    (2,),
)
@pytest.mark.asyncio
async def test_hello_failure_failure_response(nodes_with_chain):
    nodes = nodes_with_chain
    await nodes[0].dial_peer_maddr(nodes[1].listen_maddr_with_peer_id)

    async def fake_handle_hello(stream):
        await utils.read_req(stream, HelloRequest)
        # The overridden `resp_code` can be anything other than `ResponseCode.SUCCESS`
        await utils.write_resp(stream, HelloRequest(), ResponseCode.INVALID_REQUEST)
    # Mock the handler.
    nodes[1].host.set_stream_handler(REQ_RESP_HELLO_SSZ, fake_handle_hello)
    # Test: Handshake fails when the response is not success.
    with pytest.raises(HandshakeFailure):
        await nodes[0].say_hello(nodes[1].peer_id)
    await asyncio.sleep(0.01)
    assert nodes[0].peer_id not in nodes[1].handshaked_peers
