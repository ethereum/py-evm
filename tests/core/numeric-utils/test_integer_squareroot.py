from hypothesis import (
    given,
    strategies as st,
)
import pytest

from eth._utils.numeric import (
    integer_squareroot,
)


@given(st.integers(min_value=0, max_value=100))
def test_integer_squareroot_correct(value):
    result = integer_squareroot(value)
    assert (result + 1) ** 2 > value
    assert result**2 <= value


@pytest.mark.parametrize(
    "value,expected",
    (
        (0, 0),
        (1, 1),
        (2, 1),
        (3, 1),
        (4, 2),
        (27, 5),
        (65535, 255),
        (65536, 256),
        (18446744073709551615, 4294967295),
    ),
)
def test_integer_squareroot_success(value, expected):
    actual = integer_squareroot(value)
    assert actual == expected


@pytest.mark.parametrize(
    "value",
    (
        (1.5),
        (-1),
    ),
)
def test_integer_squareroot_edge_cases(value):
    with pytest.raises(ValueError):
        integer_squareroot(value)
