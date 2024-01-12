from eth_utils import (
    decode_hex,
    encode_hex,
)
from hypothesis import (
    given,
    strategies as st,
)
import pytest


@pytest.mark.parametrize(
    "value,expected",
    (
        (b"", "0x"),
        (b"\x00", "0x00"),
        (b"\x01", "0x01"),
    ),
)
def test_basic_hexadecimal_encoding(value, expected):
    actual = encode_hex(value)
    assert actual == expected


@pytest.mark.parametrize(
    "value,expected",
    (
        ("0x", b""),
        ("0x00", b"\x00"),
        ("0x01", b"\x01"),
    ),
)
def test_basic_hexadecimal_decoding(value, expected):
    actual = decode_hex(value)
    assert actual == expected


@given(value=st.binary(min_size=0, max_size=256))
def test_round_trip_with_bytestring_start(value):
    intermediate_value = encode_hex(value)
    round_trip_value = decode_hex(intermediate_value)
    assert round_trip_value == value


HEX_ALPHABET = "1234567890abcdef"


def _coerce_to_even_hex(raw_hex):
    return "0x" + raw_hex[: 2 * (len(raw_hex) // 2)]


@given(
    value=st.text(alphabet=HEX_ALPHABET, min_size=0, max_size=256).map(
        _coerce_to_even_hex
    )
)
def test_round_trip_with_hex_string_start(value):
    intermediate_value = decode_hex(value)
    round_trip_value = encode_hex(intermediate_value)
    assert round_trip_value == value
