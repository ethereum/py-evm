from .string import (
    force_bytes,
    force_text,
)
from .types import (
    is_bytes,
)


def pad_left(value, length, fill_char="0"):
    """
    Left pads a string to length
    """
    pad_length = length - len(value)
    head = b"" if is_bytes(value) else ""
    fill_value = force_bytes(fill_char) if is_bytes(value) else force_text(fill_char)
    if pad_length > 0:
        head = fill_value * pad_length
    return head + value


def pad_right(value, length, fill_char="0"):
    """
    Right pads a string to length
    """
    pad_length = length - len(value)
    tail = b"" if is_bytes(value) else ""
    fill_value = force_bytes(fill_char) if is_bytes(value) else force_text(fill_char)
    if pad_length > 0:
        tail = fill_value * pad_length
    return value + tail


def is_prefixed(value, prefix):
    return value.startswith(
        force_bytes(prefix) if is_bytes(value) else force_text(prefix)
    )


def is_0x_prefixed(value):
    return is_prefixed(value, '0x')


def remove_0x_prefix(value):
    if is_0x_prefixed(value):
        return value[2:]
    return value


def add_0x_prefix(value):
    if is_0x_prefixed(value):
        return value

    prefix = b'0x' if is_bytes(value) else '0x'
    return prefix + value
