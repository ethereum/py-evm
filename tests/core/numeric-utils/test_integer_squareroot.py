import pytest

from eth.utils.numeric import (
    integer_squareroot,
)


@pytest.mark.parametrize(
    'value,expected',
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
        (1.5, ValueError()),
        (-1, ValueError()),
    )
)
def test_integer_squareroot(value, expected):
    if isinstance(expected, Exception):
        with pytest.raises(ValueError):
            integer_squareroot(value)
    else:
        actual = integer_squareroot(value)
        assert actual == expected
