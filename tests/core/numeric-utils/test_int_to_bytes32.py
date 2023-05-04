import pytest

from eth._utils.numeric import (
    int_to_bytes32,
)
from eth.constants import (
    NULL_BYTE,
    UINT_256_MAX,
)


@pytest.mark.parametrize(
    "value, expected",
    (
        (0, NULL_BYTE * 32),
        (1, NULL_BYTE * 31 + b"\x01"),
        (UINT_256_MAX, b"\xff" * 32),
    ),
)
def test_int_to_bytes32_valid(value, expected):
    assert int_to_bytes32(value) == expected


@pytest.mark.parametrize(
    "value",
    (
        -1,
        UINT_256_MAX + 1,
    ),
)
def test_int_to_bytes32_invalid(value):
    with pytest.raises(ValueError):
        int_to_bytes32(value)
