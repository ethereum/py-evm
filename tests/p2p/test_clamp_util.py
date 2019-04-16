import pytest

from p2p._utils import clamp


@pytest.mark.parametrize(
    'lower_bound,upper_bound,value,expected',
    (
        (5, 8, 4, 5),
        (5, 8, 5, 5),
        (5, 8, 6, 6),
        (5, 8, 7, 7),
        (5, 8, 8, 8),
        (5, 8, 9, 8),
    ),
)
def test_numeric_clamp_utility(lower_bound, upper_bound, value, expected):
    result = clamp(lower_bound, upper_bound, value)
    assert result == expected
