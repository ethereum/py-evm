from typing import (
    Tuple,
    Type,
    TypeVar,
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
    ResponseCode,
)


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


MsgType = TypeVar("MsgType", bound=ssz.Serializable)


async def read_req(
    stream: INetStream,
    msg_type: Type[MsgType],
    is_first_read: bool = False,
) -> MsgType:
    return await _read_ssz_msg(stream, msg_type, is_first_read)


async def write_req(
    stream: INetStream,
    msg: MsgType,
) -> None:
    msg_bytes = _serialize_ssz_msg(msg)
    await stream.write(msg_bytes)


async def read_resp(
    stream: INetStream,
    msg_type: Type[MsgType],
    is_first_read: bool = False,
) -> Tuple[int, MsgType]:
    result_byte = await stream.read(1)
    result = result_byte[0]
    msg = await _read_ssz_msg(stream, msg_type, is_first_read)
    return result, msg


async def write_resp(
    stream: INetStream,
    msg: MsgType,
    result: int,
) -> None:
    # TODO: Confirm the endian.
    try:
        result_byte = result.to_bytes(1, "big")
    except OverflowError as e:
        raise ValueError(f"result={result} is not valid") from e
    msg_bytes = _serialize_ssz_msg(msg)
    await stream.write(result_byte + msg_bytes)


async def _read_ssz_msg(
    stream: INetStream,
    msg_type: Type[MsgType],
    is_first_read: bool = False,
) -> MsgType:
    # TODO: Confirm that `timeout` is correct.
    timeout = 10
    len_payload = await decode_uvarint_from_stream(stream, timeout)
    if len_payload > REQ_RESP_MAX_SIZE:
        raise ValueError(
            f"size_of_payload={len_payload} is larger than maximum={REQ_RESP_MAX_SIZE}"
        )
    # TODO: Add correct `timeout`.
    payload = await stream.read(len_payload)
    return ssz.decode(payload, msg_type)


def _serialize_ssz_msg(msg: MsgType) -> bytes:
    msg_bytes = ssz.encode(msg)
    len_payload_varint = encode_uvarint(len(msg_bytes))
    return len_payload_varint + msg_bytes
