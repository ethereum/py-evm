import pytest

from evm.exceptions import (
    EVMNotFound,
)

from evm.utils.ranges import (
    find_range,
)


OPEN_RANGE = ((None, None),)
LEFT_OPEN = ((None, 100),)
RIGHT_OPEN = ((10, None),)

RANGE_A = ((10, 100), (101, 200), (201, 300))
RANGE_B = ((None, 100), (101, 200), (201, 300))
RANGE_C = ((10, 100), (101, 200), (201, None))
RANGE_D = ((None, 100), (101, 200), (201, None))


@pytest.mark.parametrize(
    "ranges,block_number,expected",
    (
        (OPEN_RANGE, 0, (None, None)),
        (OPEN_RANGE, 1, (None, None)),
        (OPEN_RANGE, 10, (None, None)),
        (LEFT_OPEN, 0, (None, 100)),
        (LEFT_OPEN, 1, (None, 100)),
        (LEFT_OPEN, 100, (None, 100)),
        (LEFT_OPEN, 101, EVMNotFound),
        (LEFT_OPEN, 200, EVMNotFound),
        (RIGHT_OPEN, 0, EVMNotFound),
        (RIGHT_OPEN, 9, EVMNotFound),
        (RIGHT_OPEN, 10, (10, None)),
        (RIGHT_OPEN, 11, (10, None)),
        (RIGHT_OPEN, 10000, (10, None)),
        (RANGE_A, 0, EVMNotFound),
        (RANGE_A, 9, EVMNotFound),
        (RANGE_A, 10, (10, 100)),
        (RANGE_A, 11, (10, 100)),
        (RANGE_A, 99, (10, 100)),
        (RANGE_A, 100, (10, 100)),
        (RANGE_A, 101, (101, 200)),
        (RANGE_A, 199, (101, 200)),
        (RANGE_A, 200, (101, 200)),
        (RANGE_A, 201, (201, 300)),
        (RANGE_A, 299, (201, 300)),
        (RANGE_A, 300, (201, 300)),
        (RANGE_A, 301, EVMNotFound),
        (RANGE_B, 0, (None, 100)),
        (RANGE_B, 1, (None, 100)),
        (RANGE_B, 99, (None, 100)),
        (RANGE_B, 100, (None, 100)),
        (RANGE_B, 101, (101, 200)),
        (RANGE_B, 199, (101, 200)),
        (RANGE_B, 200, (101, 200)),
        (RANGE_B, 201, (201, 300)),
        (RANGE_B, 299, (201, 300)),
        (RANGE_B, 300, (201, 300)),
        (RANGE_B, 301, EVMNotFound),
        (RANGE_C, 0, EVMNotFound),
        (RANGE_C, 9, EVMNotFound),
        (RANGE_C, 10, (10, 100)),
        (RANGE_C, 11, (10, 100)),
        (RANGE_C, 99, (10, 100)),
        (RANGE_C, 100, (10, 100)),
        (RANGE_C, 101, (101, 200)),
        (RANGE_C, 199, (101, 200)),
        (RANGE_C, 200, (101, 200)),
        (RANGE_C, 201, (201, None)),
        (RANGE_C, 299, (201, None)),
        (RANGE_C, 300, (201, None)),
        (RANGE_C, 301, (201, None)),
        (RANGE_C, 999, (201, None)),
        (RANGE_D, 0, (None, 100)),
        (RANGE_D, 1, (None, 100)),
        (RANGE_D, 99, (None, 100)),
        (RANGE_D, 100, (None, 100)),
        (RANGE_D, 101, (101, 200)),
        (RANGE_D, 199, (101, 200)),
        (RANGE_D, 200, (101, 200)),
        (RANGE_D, 201, (201, None)),
        (RANGE_D, 299, (201, None)),
        (RANGE_D, 300, (201, None)),
        (RANGE_D, 301, (201, None)),
        (RANGE_D, 999, (201, None)),
    ),
)
def test_find_range(ranges, block_number, expected):
    if isinstance(expected, type) and issubclass(expected, Exception):
        with pytest.raises(expected):
            find_range(ranges, block_number)
    else:
        actual_range = find_range(ranges, block_number)
        assert actual_range == expected
