from cytoolz import curry

from eth2.beacon.typing import Bitfield

from .tuple import update_tuple_item


@curry
def has_voted(bitfield: Bitfield, index: int) -> bool:
    return bitfield[index]


@curry
def set_voted(bitfield: Bitfield, index: int) -> Bitfield:
    return Bitfield(update_tuple_item(bitfield, index, True))


def get_bitfield_length(bit_count: int) -> int:
    """Return the length of the bitfield for a given number of attesters in bytes."""
    return (bit_count + 7) // 8


def get_empty_bitfield(bit_count: int) -> Bitfield:
    return Bitfield((False,) * bit_count)


def get_vote_count(bitfield: Bitfield) -> int:
    return len(
        tuple(index for index in range(len(bitfield)) if has_voted(bitfield, index))
    )
