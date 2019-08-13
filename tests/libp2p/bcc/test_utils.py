import asyncio
import io
from typing import (
    NamedTuple,
)

import pytest

from eth_keys import datatypes

from trinity.protocol.bcc_libp2p.configs import (
    ResponseCode,
)
from trinity.protocol.bcc_libp2p.messages import (
    HelloRequest,
)
from trinity.protocol.bcc_libp2p.utils import (
    peer_id_from_pubkey,
    read_req,
    read_resp,
    write_req,
    write_resp,
)

from libp2p.peer.id import (
    ID,
)


def test_peer_id_from_pubkey():
    pubkey = datatypes.PublicKey(
        b'n\x85UD\xe9^\xbfo\x05\xd1z\xbd\xe5k\x87Y\xe9\xfa\xb3z:\xf8z\xc5\xd7K\xa6\x00\xbbc\xda4M\x10\x1cO\x88\tl\x82\x7f\xd7\xec6\xd8\xdc\xe2\x9c\xdcG\xa5\xea|\x9e\xc57\xf8G\xbe}\xfa\x10\xe9\x12'  # noqa: E501
    )
    peer_id_expected = ID.from_base58("QmQiv6sR3qHqhUVgC5qUBVWi8YzM6HknYbu4oQKVAqPCGF")
    assert peer_id_from_pubkey(pubkey) == peer_id_expected


class FakeNetStream:
    _queue: asyncio.Queue

    class FakeMplexConn(NamedTuple):
        peer_id: ID = ID(b"\x12\x20" + b"\x00" * 32)

    mplex_conn = FakeMplexConn()

    def __init__(self) -> None:
        self._queue = asyncio.Queue()

    async def read(self, n: int = -1) -> bytes:
        buf = io.BytesIO()
        n_read = 0
        while not self._queue.empty():
            if n != -1 and n_read >= n:
                break
            buf.write(await self._queue.get())
            n_read += 1
        return buf.getvalue()

    async def write(self, data: bytes) -> int:
        for i in data:
            await self._queue.put(i.to_bytes(1, "big"))
        return len(data)


hello_req = HelloRequest(
    fork_version=b"0000",
    finalized_root=b"1" * 32,
    finalized_epoch=2,
    head_root=b"3" * 32,
    head_slot=4,
)


@pytest.mark.parametrize(
    "msg",
    (
        hello_req,
    )
)
@pytest.mark.asyncio
async def test_read_write_req_msg(msg):
    s = FakeNetStream()
    await write_req(s, msg)
    msg_read = await read_req(s, HelloRequest)
    assert msg_read == msg


@pytest.mark.parametrize(
    "msg",
    (
        hello_req,
    )
)
@pytest.mark.asyncio
async def test_read_write_resp_msg_round_trip_success_code(msg):
    s = FakeNetStream()
    resp_code = ResponseCode.SUCCESS
    await write_resp(s, msg, resp_code)
    resp_code_read, msg_read = await read_resp(s, HelloRequest)
    assert resp_code_read == resp_code
    assert msg_read == msg
