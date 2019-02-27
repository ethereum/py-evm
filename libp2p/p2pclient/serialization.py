import asyncio
from io import (
    BytesIO,
)
from typing import (
    TypeVar,
)

from google.protobuf.message import (
    Message as PBMessage,
)

Writer = TypeVar("Writer", BytesIO, asyncio.StreamWriter)


DEFAULT_MAX_BITS: int = 64


def write_unsigned_varint(writer: Writer, integer: int, max_bits: int = DEFAULT_MAX_BITS) -> None:
    max_int: int = 1 << max_bits
    if integer < 0:
        raise ValueError(f"negative integer: {integer}")
    if integer >= max_int:
        raise ValueError(f"integer too large: {integer}")
    while True:
        value: int = integer & 0x7f
        integer >>= 7
        if integer != 0:
            value |= 0x80
        byte = value.to_bytes(1, 'big')
        writer.write(byte)
        if integer == 0:
            break


async def read_unsigned_varint(
        reader: asyncio.StreamReader,
        max_bits: int = DEFAULT_MAX_BITS) -> int:
    max_int: int = 1 << max_bits
    iteration: int = 0
    result: int = 0
    has_next: bool = True
    while has_next:
        data = await reader.readexactly(1)
        c = data[0]
        value = (c & 0x7f)
        result |= (value << (iteration * 7))
        has_next = ((c & 0x80) != 0)
        iteration += 1
        if result >= max_int:
            raise ValueError(f"varint overflowed: {result}")
    return result


async def read_pbmsg_safe(s: asyncio.StreamReader, pb_msg: PBMessage) -> None:
    len_msg_bytes = await read_unsigned_varint(s)
    msg_bytes = await s.readexactly(len_msg_bytes)
    pb_msg.ParseFromString(msg_bytes)


def serialize(pb_msg: PBMessage) -> bytes:
    size = pb_msg.ByteSize()
    s = BytesIO()
    write_unsigned_varint(s, size)
    size_prefix = s.getvalue()
    msg_bytes: bytes = pb_msg.SerializeToString()
    return size_prefix + msg_bytes
