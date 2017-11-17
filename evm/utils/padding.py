from cytoolz import (
    curry,
)


@curry
def pad_left(value, to_size, pad_with):
    """
    Should be called to pad value to expected length
    """
    pad_amount = to_size - len(value)
    if pad_amount > 0:
        return b"".join((
            pad_with * pad_amount,
            value,
        ))
    else:
        return value


@curry
def pad_right(value, to_size, pad_with):
    """
    Should be called to pad value to expected length
    """
    pad_amount = to_size - len(value)
    if pad_amount > 0:
        return b"".join((
            value,
            pad_with * pad_amount,
        ))
    else:
        return value


zpad_right = pad_right(pad_with=b'\x00')
zpad_left = pad_left(pad_with=b'\x00')

pad32 = zpad_left(to_size=32)
pad32r = zpad_right(to_size=32)
