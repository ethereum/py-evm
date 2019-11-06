import asyncio
from typing import NamedTuple

from eth.exceptions import BlockNotFound
from eth_keys import datatypes
from libp2p.peer.id import ID
import pytest

from trinity.protocol.bcc_libp2p.configs import ResponseCode
from trinity.protocol.bcc_libp2p.exceptions import (
    InvalidRequestSaidPeer,
    ReadMessageFailure,
    ServerErrorSaidPeer,
    WriteMessageFailure,
)
from trinity.protocol.bcc_libp2p.messages import HelloRequest
from trinity.protocol.bcc_libp2p.utils import (
    get_blocks_from_canonical_chain_by_slot,
    get_blocks_from_fork_chain_by_root,
    peer_id_from_pubkey,
    read_req,
    read_resp,
    write_req,
    write_resp,
)
from trinity.tools.bcc_factories import BeaconBlockFactory

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
    msg_read = await read_resp(s, type(msg))
    assert msg_read == msg


@pytest.mark.parametrize(
    "resp_code, error_cls, error_msg",
    (
        (ResponseCode.INVALID_REQUEST, InvalidRequestSaidPeer, "error msg"),
        (ResponseCode.SERVER_ERROR, ServerErrorSaidPeer, "error msg"),
    ),
)
@pytest.mark.asyncio
async def test_read_write_resp_msg_error_resp_code(resp_code, error_cls, error_msg):
    s = FakeNetStream()
    await write_resp(s, error_msg, resp_code)
    with pytest.raises(error_cls, match=error_msg):
        await read_resp(s, HelloRequest)


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


@pytest.mark.parametrize(
    "db_block_slots, slot_of_requested_blocks, expected_block_slots",
    (
        (range(5), [0, 2, 4], [0, 2, 4]),
        ([1, 3, 5], [0, 2, 4], []),
        ([2, 4], range(5), [2, 4]),
    ),
)
@pytest.mark.asyncio
async def test_get_blocks_from_canonical_chain_by_slot(
    db_block_slots, slot_of_requested_blocks, expected_block_slots
):
    chain = BeaconBlockFactory.create_branch_by_slots(db_block_slots)
    # Mock up block database
    mock_slot_to_block_db = {block.slot: block for block in chain}

    class Chain:
        def get_canonical_block_by_slot(self, slot):
            if slot in mock_slot_to_block_db:
                return mock_slot_to_block_db[slot]
            else:
                raise BlockNotFound

    result_blocks = get_blocks_from_canonical_chain_by_slot(
        chain=Chain(), slot_of_requested_blocks=slot_of_requested_blocks
    )

    expected_blocks = [mock_slot_to_block_db[slot] for slot in expected_block_slots]
    assert len(result_blocks) == len(expected_blocks)
    assert set(result_blocks) == set(expected_blocks)


@pytest.mark.parametrize(
    "fork_chain_block_slots, slot_of_requested_blocks, expected_block_slots",
    (
        (range(10), [1, 4], [1, 4]),
        ([0, 2, 3, 7, 8], list(range(1, 9, 2)), [3, 7]),
        ([0, 2, 5], list(range(1, 6)), [2, 5]),
        ([0, 4, 5], [2, 3], []),
    ),
)
@pytest.mark.asyncio
async def test_get_blocks_from_fork_chain_by_root(
    fork_chain_block_slots, slot_of_requested_blocks, expected_block_slots
):
    fork_chain_blocks = BeaconBlockFactory.create_branch_by_slots(
        fork_chain_block_slots
    )
    mock_root_to_block_db = {block.signing_root: block for block in fork_chain_blocks}

    class Chain:
        def get_block_by_root(self, root):
            if root in mock_root_to_block_db:
                return mock_root_to_block_db[root]
            else:
                raise BlockNotFound

    requested_blocks = get_blocks_from_fork_chain_by_root(
        chain=Chain(),
        start_slot=slot_of_requested_blocks[0],
        peer_head_block=fork_chain_blocks[-1],
        slot_of_requested_blocks=slot_of_requested_blocks,
    )

    expected_blocks = [
        block for block in fork_chain_blocks if block.slot in expected_block_slots
    ]
    assert len(requested_blocks) == len(expected_blocks)
    assert set(requested_blocks) == set(expected_blocks)
