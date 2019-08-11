import asyncio
from typing import (
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
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
from libp2p.stream_muxer.mplex.utils import (
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


MsgType = TypeVar("MsgType", bound=ssz.Serializable)
ErrorMsgType = TypeVar("ErrorMsgType", bound=str)


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


async def read_req(
    stream: INetStream,
    msg_type: Type[MsgType],
) -> MsgType:
    return await _read_ssz_msg(stream, msg_type, timeout=RESP_TIMEOUT)


async def write_req(
    stream: INetStream,
    msg: MsgType,
) -> None:
    msg_bytes = _serialize_ssz_msg(msg)
    await stream.write(msg_bytes)


async def read_resp(
    stream: INetStream,
    msg_type: Type[MsgType],
) -> Tuple[ResponseCode, Union[MsgType, ErrorMsgType]]:
    result_byte = await asyncio.wait_for(stream.read(1), timeout=TTFB_TIMEOUT)
    resp_code = ResponseCode.from_bytes(result_byte)
    # `MsgType`
    msg: Union[MsgType, ErrorMsgType]
    if resp_code == ResponseCode.SUCCESS:
        msg = await _read_ssz_msg(stream, msg_type, timeout=RESP_TIMEOUT)
    # `ErrorMsgType`
    else:
        msg_bytes = await _read_varint_prefixed_bytes(stream, timeout=RESP_TIMEOUT)
        msg = cast(ErrorMsgType, msg_bytes.decode("utf-8"))
    return resp_code, msg


async def write_resp(
    stream: INetStream,
    msg: Union[MsgType, ErrorMsgType],
    resp_code: ResponseCode,
) -> None:
    try:
        resp_code_byte = resp_code.to_bytes()
    except OverflowError as e:
        raise ValueError(f"result={resp_code} is not valid") from e
    # `ErrorMsgType`
    if isinstance(msg, str):
        msg_bytes = _serialize_bytes(msg.encode("utf-8"))
    # `MsgType`
    elif isinstance(msg, ssz.Serializable):
        msg_bytes = _serialize_ssz_msg(msg)
    else:
        raise TypeError(
            "Type of `msg` should be either `str` or `ssz.Serializable`"
        )
    # TODO: Optimization: probably the first byte should be written
    #   at the beginning of this function, to meet the limitation of `TTFB_TIMEOUT`.
    await stream.write(resp_code_byte + msg_bytes)


async def _read_varint_prefixed_bytes(
    stream: INetStream,
    timeout: float = None,
) -> bytes:
    len_payload = await decode_uvarint_from_stream(stream, timeout)
    if len_payload > REQ_RESP_MAX_SIZE:
        raise ValueError(
            f"size_of_payload={len_payload} is larger than maximum={REQ_RESP_MAX_SIZE}"
        )
    payload = await asyncio.wait_for(stream.read(len_payload), timeout)
    return payload


async def _read_ssz_msg(
    stream: INetStream,
    msg_type: Type[MsgType],
    timeout: float = None,
) -> MsgType:
    payload = await _read_varint_prefixed_bytes(stream, timeout=timeout)
    return ssz.decode(payload, msg_type)


def _serialize_bytes(payload: bytes) -> bytes:
    len_payload_varint = encode_uvarint(len(payload))
    return len_payload_varint + payload


def _serialize_ssz_msg(msg: MsgType) -> bytes:
    msg_bytes = ssz.encode(msg)
    return _serialize_bytes(msg_bytes)
