import pytest

from hypothesis import (
    given,
    strategies as st,
)

from evm.utils.encoding import (
    encode_hex,
    decode_hex,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        ('myString', '0x6d79537472696e67'),
        ('myString\x00', '0x6d79537472696e6700'),
        (
            b'\xd9e\x11\xbe\xdbj\x81Q\xea\xb5\x9et\xd6l\r\xa7\xdfc\x14c\xb8b\x1ap\x8e@\x93\xe6\xec\xd7P\x8a',
            '0xd96511bedb6a8151eab59e74d66c0da7df631463b8621a708e4093e6ecd7508a',
        )
    ]
)
def test_encode_hex(value, expected):
    assert encode_hex(value) == expected


@given(value=st.binary(min_size=0, average_size=32, max_size=256))
def test_hex_encode_decode_round_trip(value):
    intermediate_value = encode_hex(value)
    result_value = decode_hex(intermediate_value)
    assert result_value == value, "Expected: {0!r}, Result: {1!r}, Intermediate: {2!r}".format(value, result_value, intermediate_value)
