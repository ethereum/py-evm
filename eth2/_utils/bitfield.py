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
from eth2.beacon.typing import Bitfield


@curry
def has_voted(bitfield: Bitfield, index: int) -> bool:
    byte_index = index // 8
    bit_index = index % 8
    return bool((bitfield[byte_index] >> bit_index) % 2)


@curry
def set_voted(bitfield: Bitfield, index: int) -> Bitfield:
    byte_index = index // 8
    bit_index = index % 8
    new_byte_value = bitfield[byte_index] | (1 << bit_index)
    new_bitfield = bitfield[:byte_index] + bytes([new_byte_value]) + bitfield[byte_index + 1:]
    return Bitfield(new_bitfield)


def get_bitfield_length(bit_count: int) -> int:
    """Return the length of the bitfield for a given number of attesters in bytes."""
    return (bit_count + 7) // 8


def get_empty_bitfield(bit_count: int) -> Bitfield:
    return Bitfield(b"\x00" * get_bitfield_length(bit_count))


def get_vote_count(bitfield: Bitfield) -> int:
    return len(
        tuple(
            index
            for index in range(len(bitfield) * 8)
            if has_voted(bitfield, index)
        )
    )


def or_bitfields(bitfields: List[Bitfield]) -> Bitfield:
    byte_slices = zip_longest(*bitfields)

    if len(set((len(b) for b in bitfields))) != 1:
        raise ValueError("The bitfield sizes are different")

    return Bitfield(bytes(map(reduce(operator.or_), byte_slices)))
