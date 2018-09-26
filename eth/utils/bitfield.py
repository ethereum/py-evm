from typing import (
    List,
)


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
    votes = 0
    for index in range(len(bitfield) * 8):
        if has_voted(bitfield, index):
            votes += 1
    return votes


def or_bitfields(bitfields: List[bytes]) -> bytes:
    new = b''
    for i in range(len(bitfields[0])):
        byte = 0
        for bitfield in bitfields:
            byte = bitfield[i] | byte
        new += bytes([byte])
    return new
