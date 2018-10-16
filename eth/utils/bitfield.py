import operator

from typing import (
    List,
)
from cytoolz import (
    curry,
)
from cytoolz.curried import reduce
from itertools import (
    zip_longest,
)


@curry
def has_voted(bitfield: bytes, index: int) -> bool:
    return bool(bitfield[index // 8] & (128 >> (index % 8)))


@curry
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
    byte_slices = zip_longest(*bitfields)

    if len(set((len(b) for b in bitfields))) != 1:
        raise ValueError("The bitfield sizes are different")

    return bytes(map(reduce(operator.or_), byte_slices))
