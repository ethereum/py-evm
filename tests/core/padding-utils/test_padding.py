import pytest

from evm.utils.padding import (
    pad_left,
    pad_right,
    pad32,
    pad32r
)

padding_byte = b"\x00"


@pytest.mark.parametrize(
    "value, to_size, pad_with, expected",
    (
        (b"", 0, b"\x00", b""),
        (b"", 1, b"\x00", b"\x00"),
        (b"\x00", 1, b"\x01", b"\x00"),
        (b"\x00", 2, b"\x01", b"\x01\x00")
    )
)
def test_pad_left(value, to_size, pad_with, expected):
    assert pad_left(value, to_size, pad_with) == expected


@pytest.mark.parametrize(
    "value, to_size, pad_with, expected",
    (
        (b"", 0, b"\x00", b""),
        (b"", 1, b"\x00", b"\x00"),
        (b"\x00", 1, b"\x01", b"\x00"),
        (b"\x00", 2, b"\x01", b"\x00\x01")
    )
)
def test_pad_right(value, to_size, pad_with, expected):
    assert pad_right(value, to_size, pad_with) == expected


@pytest.mark.parametrize(
    "value, expected",
    (
        (b"", padding_byte * 32),
        (b"\x01", (padding_byte * 31) + b"\x01")
    )
)
def test_pad_32(value, expected):
    assert pad32(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    (
        (b"", padding_byte * 32),
        (b"\x01", b"\x01" + (padding_byte * 31))
    )
)
def test_pad_32r(value, expected):
    assert pad32r(value) == expected
