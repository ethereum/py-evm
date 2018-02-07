import pytest

from evm.utils.numeric import (
    int_to_bytes32,
)


@pytest.mark.parametrize(
    'value, expected',
    (
        (0, b'\x00' * 32),
        (1, b'\x00' * 31 + b'\x01'),
        ((2 ** 256) - 1, b'\xff' * 32),
    )
)
def test_int_to_bytes32_valid(value, expected):
    assert int_to_bytes32(value) == expected


@pytest.mark.parametrize(
    'value, ErrorType',
    (
        (-1, OverflowError),
        (2 ** 256, ValueError),
    )
)
def test_int_to_bytes32_invalid(value, ErrorType):
    with pytest.raises(ErrorType):
        int_to_bytes32(value)
