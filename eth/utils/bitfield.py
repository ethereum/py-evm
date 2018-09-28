from typing import (
    List,
)
from cytoolz import (
    curry,
)


@curry
def has_voted(bitfield: bytes, index: int) -> bool:
    return bool(bitfield[index // 8] & (128 >> (index % 8)))


def set_voted(bitfield: bytes, index: int) -> bytes:
    byte_index = index // 8
    bit_index = index % 8
    new_byte_value = bitfield[byte_index] | (128 >> bit_index)
    return bitfield[:byte_index] + bytes([new_byte_value]) + bitfield[byte_index + 1:]


def get_bitfield_length(bit_count: int) -> int:
    """Return the length of the bitfield for a given number of attesters in bytes."""
    return (bit_count + 7) // 8


def get_empty_bitfield(bit_count: int) -> bytes:
    return b"\x00" * get_bitfield_length(bit_count)


def get_vote_count(bitfield: bytes) -> int:
    return len(
        tuple(
            index
            for index in range(len(bitfield) * 8)
            if has_voted(bitfield, index)
        )
    )


def or_bitfields(bitfields: List[bytes]) -> bytes:
    bytes_length = len(bitfields[0])
    new = b''
    for i in range(bytes_length):
        byte = 0
        for bitfield in bitfields:
            if len(bitfield) != bytes_length:
                raise ValueError("The bitfield sizes are different")
            if i < len(bitfield):
                byte = bitfield[i] | byte
        new += bytes([byte])
    return new
