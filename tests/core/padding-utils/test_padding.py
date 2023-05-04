import pytest

from eth._utils.padding import (
    pad32,
    pad32r,
)

padding_byte = b"\x00"


@pytest.mark.parametrize(
    "value, expected",
    ((b"", padding_byte * 32), (b"\x01", (padding_byte * 31) + b"\x01")),
)
def test_pad_32(value, expected):
    assert pad32(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    ((b"", padding_byte * 32), (b"\x01", b"\x01" + (padding_byte * 31))),
)
def test_pad_32r(value, expected):
    assert pad32r(value) == expected
