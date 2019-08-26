import asyncio
from typing import NamedTuple

from eth_keys import datatypes
from libp2p.peer.id import ID
import pytest

from trinity.protocol.bcc_libp2p.configs import ResponseCode
from trinity.protocol.bcc_libp2p.exceptions import (
    ReadMessageFailure,
    WriteMessageFailure,
)
from trinity.protocol.bcc_libp2p.messages import HelloRequest
from trinity.protocol.bcc_libp2p.utils import (
    peer_id_from_pubkey,
    read_req,
    read_resp,
    write_req,
    write_resp,
)

# Wrong type of `fork_version`, which should be `bytes4`.
invalid_ssz_msg = HelloRequest(fork_version="1")


def test_peer_id_from_pubkey():
    pubkey = datatypes.PublicKey(
        b"n\x85UD\xe9^\xbfo\x05\xd1z\xbd\xe5k\x87Y\xe9\xfa\xb3z:\xf8z\xc5\xd7K\xa6\x00\xbbc\xda4M\x10\x1cO\x88\tl\x82\x7f\xd7\xec6\xd8\xdc\xe2\x9c\xdcG\xa5\xea|\x9e\xc57\xf8G\xbe}\xfa\x10\xe9\x12"  # noqa: E501
    )
    peer_id_expected = ID.from_base58("QmQiv6sR3qHqhUVgC5qUBVWi8YzM6HknYbu4oQKVAqPCGF")
    assert peer_id_from_pubkey(pubkey) == peer_id_expected


class FakeNetStream:
    _queue: "asyncio.Queue[bytes]"

    class FakeMplexConn(NamedTuple):
        peer_id: ID = ID(b"\x12\x20" + b"\x00" * 32)

    mplex_conn = FakeMplexConn()

    def __init__(self) -> None:
        self._queue = asyncio.Queue()

    async def read(self, n: int = -1) -> bytes:
        buf = bytearray()
        # Exit with empty bytes directly if `n == 0`.
        if n == 0:
            return b""
        # Force to blocking wait for first byte.
        buf.extend(await self._queue.get())
        while not self._queue.empty():
            if n != -1 and len(buf) >= n:
                break
            buf.extend(await self._queue.get())
        return bytes(buf)

    async def write(self, data: bytes) -> int:
        for i in data:
            await self._queue.put(i.to_bytes(1, "big"))
        return len(data)


@pytest.mark.parametrize("msg", (HelloRequest(),))
@pytest.mark.asyncio
async def test_read_write_req_msg(msg):
    s = FakeNetStream()
    await write_req(s, msg)
    msg_read = await read_req(s, type(msg))
    assert msg_read == msg


@pytest.mark.parametrize("msg", (HelloRequest(),))
@pytest.mark.asyncio
async def test_read_write_resp_msg(msg):
    s = FakeNetStream()
    resp_code = ResponseCode.SUCCESS
    await write_resp(s, msg, resp_code)
    resp_code_read, msg_read = await read_resp(s, type(msg))
    assert resp_code_read == resp_code
    assert msg_read == msg


@pytest.mark.parametrize(
    "resp_code, error_msg",
    (
        (ResponseCode.INVALID_REQUEST, "error msg"),
        (ResponseCode.SERVER_ERROR, "error msg"),
    ),
)
@pytest.mark.asyncio
async def test_read_write_resp_msg_error_resp_code(resp_code, error_msg):
    s = FakeNetStream()
    await write_resp(s, error_msg, resp_code)
    resp_code_read, msg_read = await read_resp(s, HelloRequest)
    assert resp_code_read == resp_code
    assert msg_read == error_msg


@pytest.mark.asyncio
async def test_read_req_failure(mock_timeout):
    s = FakeNetStream()
    # Test: Raise `ReadMessageFailure` if the time is out.
    with pytest.raises(ReadMessageFailure):
        await read_req(s, HelloRequest)

    await s.write(b"\x03123")
    with pytest.raises(ReadMessageFailure):
        await read_req(s, HelloRequest)


@pytest.mark.asyncio
async def test_write_req_failure():
    s = FakeNetStream()

    # Test: Raise `WriteMessageFailure` if `ssz.SerializationError` is thrown.
    with pytest.raises(WriteMessageFailure):
        await write_req(s, invalid_ssz_msg)


@pytest.mark.asyncio
async def test_read_resp_failure(monkeypatch, mock_timeout):
    s = FakeNetStream()
    # Test: Raise `ReadMessageFailure` if the time is out.
    with pytest.raises(ReadMessageFailure):
        await read_resp(s, HelloRequest)

    # Test: Raise `ReadMessageFailure` if `read` returns `b""`.

    async def _fake_read(n):
        return b""

    monkeypatch.setattr(s, "read", _fake_read)
    with pytest.raises(ReadMessageFailure):
        await read_resp(s, HelloRequest)


@pytest.mark.parametrize(
    "msg_bytes",
    (
        b"\x7b\x03msg",  # resp_code = 123, msg = "msg"
        # Should probably be reserved as a valid error code in the future.
        b"\xff\x03msg",  # resp_code = 255, msg = "msg"
    ),
)
@pytest.mark.asyncio
async def test_read_resp_failure_invalid_resp_code(msg_bytes):
    s = FakeNetStream()
    await s.write(msg_bytes)
    with pytest.raises(ReadMessageFailure):
        await read_resp(s, HelloRequest)


@pytest.mark.asyncio
async def test_write_resp_failure():
    s = FakeNetStream()
    # Test: Raise `WriteMessageFailure` if `resp_code` is SUCCESS,
    #   but `msg` is not `ssz.Serializable`.
    with pytest.raises(WriteMessageFailure):
        await write_resp(s, "error msg", ResponseCode.SUCCESS)

    # Test: Raise `WriteMessageFailure` if `resp_code` is not SUCCESS,
    #   but `msg` is not `str`.
    with pytest.raises(WriteMessageFailure):
        await write_resp(s, HelloRequest(), ResponseCode.INVALID_REQUEST)

    # Test: Raise `WriteMessageFailure` if `ssz.SerializationError` is thrown.
    with pytest.raises(WriteMessageFailure):
        await write_req(s, invalid_ssz_msg)
