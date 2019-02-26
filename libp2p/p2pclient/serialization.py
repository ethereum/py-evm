import asyncio
from io import (
    BytesIO,
)
from typing import (
    Any,
    Awaitable,
    Callable,
    TypeVar,
)


Writer = TypeVar("Writer", BytesIO, asyncio.StreamWriter)


def write_varint(writer: Writer, integer: int) -> None:
    # TODO: handle negative integers
    if integer < 0:
        raise ValueError(f"Negative integer: {integer}")
    while True:
        value = integer & 0x7f
        integer >>= 7
        if integer != 0:
            value |= 0x80
        byte = value.to_bytes(1, 'big')
        writer.write(byte)
        if integer == 0:
            break


# TODO: pb typing
async def read_byte(reader: asyncio.StreamReader) -> int:
    data = await reader.readexactly(1)
    return data[0]


# TODO: pb typing
async def read_varint(
        reader: asyncio.StreamReader,
        read_byte: Callable[[asyncio.StreamReader], Awaitable[int]]) -> int:
    iteration: int = 0
    chunk_bits: int = 7
    result: int = 0
    has_next: bool = True
    while has_next:
        c = await read_byte(reader)
        value = (c & 0x7f)
        result |= (value << (iteration * chunk_bits))
        has_next = ((c & 0x80) != 0)
        iteration += 1
        # valid `iteration` should be <= 10.
        # if `iteration` == 10, then there should be only 1 bit useful in the `value`
        # in the last iteration, assuming the max size of the number is 64 bits
        if iteration > 10 or ((iteration == 10) and (value > 1)):
            raise OverflowError("Varint overflowed")
    return result


# TODO: pb_msg should be typed more accurately
async def read_pbmsg_safe(s: asyncio.StreamReader, pb_msg: Any) -> None:
    len_msg_bytes = await read_varint(s, read_byte)
    msg_bytes = await s.readexactly(len_msg_bytes)
    pb_msg.ParseFromString(msg_bytes)


# TODO: pb_msg should be typed more accurately
def serialize(pb_msg: Any) -> bytes:
    size = pb_msg.ByteSize()
    s = BytesIO()
    write_varint(s, size)
    size_prefix = s.getvalue()
    return size_prefix + pb_msg.SerializeToString()
