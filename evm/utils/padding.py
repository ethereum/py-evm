from cytoolz import (
    curry,
)


ZERO_BYTE = b'\x00'


@curry
def zpad_right(value, to_size):
    return value.ljust(to_size, ZERO_BYTE)


@curry
def zpad_left(value, to_size):
    return value.rjust(to_size, ZERO_BYTE)


pad32 = zpad_left(to_size=32)
pad32r = zpad_right(to_size=32)
