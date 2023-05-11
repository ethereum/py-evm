import pytest

from eth._utils.numeric import (
    get_highest_bit_index,
)


@pytest.mark.parametrize(
    "value,expected",
    (
        (1, 0),
        (2, 1),
        (3, 1),
        (255, 7),
        (256, 8),
    ),
)
def test_get_highest_bit_index(value, expected):
    actual = get_highest_bit_index(value)
    assert actual == expected
