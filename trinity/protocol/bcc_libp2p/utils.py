import asyncio
from typing import (
    Type,
    TypeVar,
    Union,
)

from eth_keys import datatypes

from multiaddr import Multiaddr

import multihash

from libp2p.network.stream.net_stream_interface import (
    INetStream,
)
from libp2p.peer.id import (
    ID,
)
from libp2p.utils import (
    decode_uvarint_from_stream,
    encode_uvarint,
)

import ssz

from .configs import (
    REQ_RESP_ENCODE_POSTFIX,
    REQ_RESP_PROTOCOL_PREFIX,
    REQ_RESP_VERSION,
    REQ_RESP_MAX_SIZE,
    RESP_TIMEOUT,
    ResponseCode,
    TTFB_TIMEOUT,
)
from .exceptions import (
    ReadMessageFailure,
    WriteMessageFailure,
    ResponseFailure,
)
from libp2p.network.stream.exceptions import StreamEOF, StreamReset


MsgType = TypeVar("MsgType", bound=ssz.Serializable)


def peer_id_from_pubkey(pubkey: datatypes.PublicKey) -> ID:
    algo = multihash.Func.sha2_256
    mh_digest = multihash.digest(pubkey.to_bytes(), algo)
    return ID(mh_digest.encode())


def make_tcp_ip_maddr(ip: str, port: int) -> Multiaddr:
    return Multiaddr(f"/ip4/{ip}/tcp/{port}")


def make_rpc_protocol_id(message_name: str, schema_version: str, encoding: str) -> str:
    return f"{REQ_RESP_PROTOCOL_PREFIX}/{message_name}/{schema_version}/{encoding}"


def make_rpc_v1_ssz_protocol_id(message_name: str) -> str:
    return make_rpc_protocol_id(message_name, REQ_RESP_VERSION, REQ_RESP_ENCODE_POSTFIX)


# TODO: Refactor: Probably move these [de]serialization functions to `Node` as methods,
#   expose the hard-coded to parameters, and pass the timeout from the methods?

class Interaction:
    stream: INetStream

    def __init__(self, stream: INetStream):
        self.stream = stream

    async def write_request(self, message: MsgType) -> None:
        await write_req(self.stream, message)

    async def respond(self, message: MsgType) -> None:
        await write_resp(self.stream, message, ResponseCode.SUCCESS)

    async def read_request(self, message_type: Type[MsgType]) -> MsgType:
        return await read_req(self.stream, message_type)

    async def read_response(self, message_type: Type[MsgType]) -> MsgType:
        return await read_resp(self.stream, message_type)

    @property
    def peer_id(self) -> ID:
        return self.stream.mplex_conn.peer_id


async def read_req(
    stream: INetStream,
    msg_type: Type[MsgType],
) -> MsgType:
    """
    Read a `MsgType` request message from the `stream`.
    `ReadMessageFailure` is raised if fail to read the message.
    """
    return await _read_ssz_stream(stream, msg_type, timeout=RESP_TIMEOUT)


async def write_req(
    stream: INetStream,
    msg: MsgType,
) -> None:
    """
    Write the request `msg` to the `stream`.
    `WriteMessageFailure` is raised if fail to write the message.
    """
    msg_bytes = _serialize_ssz_msg(msg)
    # TODO: Handle exceptions from stream?
    await _write_stream(stream, msg_bytes)


async def read_resp(
    stream: INetStream,
    msg_type: Type[MsgType],
) -> MsgType:
    """
    Read a `MsgType` response message from the `stream`.
    `ReadMessageFailure` is raised if fail to read the message.
    Returns the error message(type `str`) if the response code is not SUCCESS, otherwise returns
    the `MsgType` response message.
    """
    result_bytes = await _read_stream(stream, 1, TTFB_TIMEOUT)
    if len(result_bytes) != 1:
        raise ReadMessageFailure(
            f"result bytes should be of length 1: result_bytes={result_bytes}"
        )
    try:
        resp_code = ResponseCode(result_bytes[0])
    except ValueError:
        raise ReadMessageFailure(f"unknown resp_code={result_bytes[0]}")
    if resp_code == ResponseCode.SUCCESS:
        return await _read_ssz_stream(stream, msg_type, timeout=RESP_TIMEOUT)
    # error message
    else:
        msg_bytes = await _read_varint_prefixed_bytes(stream, timeout=RESP_TIMEOUT)
        msg = msg_bytes.decode("utf-8")
        raise ResponseFailure(msg)


async def write_resp(
    stream: INetStream,
    msg: Union[MsgType, str],
    resp_code: ResponseCode,
) -> None:
    """
    Write either a `MsgType` response message or an error message to the `stream`.
    `WriteMessageFailure` is raised if fail to read the message.
    """
    try:
        resp_code_byte = resp_code.value.to_bytes(1, "big")
    except OverflowError as error:
        raise WriteMessageFailure(f"resp_code={resp_code} is not valid") from error
    msg_bytes: bytes
    # MsgType: `msg` is of type `ssz.Serializable` if response code is success.
    if resp_code == ResponseCode.SUCCESS:
        if isinstance(msg, ssz.Serializable):
            msg_bytes = _serialize_ssz_msg(msg)
        else:
            raise WriteMessageFailure(
                "type of `msg` should be `ssz.Serializable` if response code is SUCCESS, "
                f"type(msg)={type(msg)}"
            )
    # error msg is of type `str` if response code is not SUCCESS.
    else:
        if isinstance(msg, str):
            msg_bytes = _serialize_bytes(msg.encode("utf-8"))
        else:
            raise WriteMessageFailure(
                "type of `msg` should be `str` if response code is not SUCCESS, "
                f"type(msg)={type(msg)}"
            )
    # TODO: Optimization: probably the first byte should be written
    #   at the beginning of this function, to meet the limitation of `TTFB_TIMEOUT`.
    # TODO: Handle exceptions from stream?
    await _write_stream(stream, resp_code_byte + msg_bytes)


async def _write_stream(stream: INetStream, data: bytes) -> None:
    try:
        await stream.write(data)
    except StreamEOF as error:
        await stream.close()
        raise WriteMessageFailure() from error
    except StreamReset as error:
        raise WriteMessageFailure() from error


async def _read_stream(stream: INetStream, len_payload: int, timeout: float) -> bytes:
    try:
        return await asyncio.wait_for(stream.read(len_payload), timeout)
    except asyncio.TimeoutError as error:
        raise ReadMessageFailure("Timeout")
    except StreamEOF as error:
        await stream.close()
        raise ReadMessageFailure() from error
    except StreamReset as error:
        raise ReadMessageFailure() from error


async def _decode_uvarint_from_stream(stream: INetStream, timeout: float) -> None:
    try:
        return await asyncio.wait_for(decode_uvarint_from_stream(stream), timeout)
    except asyncio.TimeoutError as error:
        raise ReadMessageFailure("Timeout")
    except StreamEOF as error:
        await stream.close()
        raise ReadMessageFailure() from error
    except StreamReset as error:
        raise ReadMessageFailure() from error


async def _read_varint_prefixed_bytes(
    stream: INetStream,
    timeout: float = None,
) -> bytes:
    len_payload = await _decode_uvarint_from_stream(stream, timeout)
    if len_payload > REQ_RESP_MAX_SIZE:
        raise ReadMessageFailure(
            f"size_of_payload={len_payload} is larger than maximum={REQ_RESP_MAX_SIZE}"
        )
    payload = await _read_stream(stream, len_payload, timeout)
    if len(payload) != len_payload:
        raise ReadMessageFailure(f"expected {len_payload} bytes, but only read {len(payload)}")
    return payload


async def _read_ssz_stream(
    stream: INetStream,
    msg_type: Type[MsgType],
    timeout: float = None,
) -> MsgType:
    payload = await _read_varint_prefixed_bytes(stream, timeout=timeout)
    return _read_ssz_msg(payload, msg_type)


def _read_ssz_msg(
    payload: bytes,
    msg_type: Type[MsgType],
) -> MsgType:
    try:
        return ssz.decode(payload, msg_type)
    except (TypeError, ssz.DeserializationError) as error:
        raise ReadMessageFailure("failed to read the payload") from error


def _serialize_bytes(payload: bytes) -> bytes:
    len_payload_varint = encode_uvarint(len(payload))
    return len_payload_varint + payload


def _serialize_ssz_msg(msg: MsgType) -> bytes:
    try:
        msg_bytes = ssz.encode(msg)
        return _serialize_bytes(msg_bytes)
    except ssz.SerializationError as error:
        raise WriteMessageFailure(f"failed to serialize msg={msg}") from error
