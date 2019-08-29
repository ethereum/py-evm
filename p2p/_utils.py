import collections
from typing import Hashable, Sequence, Tuple, TypeVar

import rlp


def sxor(s1: bytes, s2: bytes) -> bytes:
    if len(s1) != len(s2):
        raise ValueError("Cannot sxor strings of different length")
    return bytes(x ^ y for x, y in zip(s1, s2))


def roundup_16(x: int) -> int:
    """Rounds up the given value to the next multiple of 16."""
    remainder = x % 16
    if remainder != 0:
        x += 16 - remainder
    return x


def get_devp2p_cmd_id(msg: bytes) -> int:
    """Return the cmd_id for the given devp2p msg.

    The cmd_id, also known as the payload type, is always the first entry of the RLP, interpreted
    as an integer.
    """
    return rlp.decode(msg[:1], sedes=rlp.sedes.big_endian_int)


def trim_middle(arbitrary_string: str, max_length: int) -> str:
    """
    Trim down strings to max_length by cutting out the middle.
    This assumes that the most "interesting" bits are toward
    the beginning and the end.

    Adds a highly unusual '✂✂✂' in the middle where characters
    were stripped out, to avoid not realizing about the stripped
    info.
    """
    # candidate for moving to eth-utils, if we like it
    size = len(arbitrary_string)
    if size <= max_length:
        return arbitrary_string
    else:
        half_len, is_odd = divmod(max_length, 2)
        first_half = arbitrary_string[:half_len - 1]
        last_half_len = half_len - 2 + is_odd
        if last_half_len > 0:
            last_half = arbitrary_string[last_half_len * -1:]
        else:
            last_half = ''
        return f"{first_half}✂✂✂{last_half}"


TValue = TypeVar('TValue', bound=Hashable)


def duplicates(elements: Sequence[TValue]) -> Tuple[TValue, ...]:
    return tuple(
        value for
        value, count in
        collections.Counter(elements).items()
        if count > 1
    )
