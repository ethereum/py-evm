import pytest

from eth.beacon.utils.random import (
    shuffle,
)


@pytest.mark.parametrize(
    (
        'values,seed,expect'
    ),
    [
        (
            tuple(range(100)),
            b'\x32' * 32,
            (
                92, 18, 80, 86, 39, 56, 81, 74, 68, 64,
                52, 82, 26, 25, 45, 2, 66, 38, 35, 15,
                46, 9, 65, 55, 85, 51, 53, 95, 57, 88,
                43, 70, 22, 5, 31, 63, 90, 61, 89, 24,
                6, 94, 12, 29, 84, 72, 42, 73, 40, 48,
                16, 77, 69, 4, 14, 75, 21, 17, 54, 37,
                98, 3, 60, 36, 76, 1, 97, 0, 44, 19,
                83, 28, 41, 47, 13, 91, 93, 7, 71, 58,
                11, 20, 50, 30, 34, 49, 33, 59, 79, 62,
                67, 96, 78, 8, 10, 99, 87, 27, 32, 23,
            ),
        ),
        (
            tuple(range(12)),
            b'\x23' * 32,
            (11, 4, 9, 5, 7, 10, 2, 8, 0, 6, 3, 1),
        ),
    ],
)
def test_shuffle_consistent(values, seed, expect):
    assert shuffle(values, seed) == expect


def test_shuffle_out_of_bound():
    values = [i for i in range(2**24 + 1)]
    with pytest.raises(ValueError):
        shuffle(values, b'hello')
