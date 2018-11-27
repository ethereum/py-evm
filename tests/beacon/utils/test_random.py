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
            [i for i in range(100)],
            b"\x8d\x8dd\xb9\x84\x05*Bw\xf5\x87\xdd\x04nj\xee\x82\xfc9\xb9\x19\x82'x!#p];\xa5\x8e\xc9",  # noqa: E501
            (87, 32, 76, 41, 61, 9, 44, 78, 70, 42, 8, 6, 79, 37, 4, 67, 3, 66, 55, 0, 69, 98, 38, 47, 20, 31, 48, 97, 34, 33, 96, 63, 91, 15, 1, 77, 39, 64, 58, 53, 82, 49, 26, 29, 5, 65, 19, 86, 74, 23, 46, 14, 10, 51, 85, 89, 57, 73, 71, 52, 88, 30, 16, 81, 24, 22, 36, 45, 12, 2, 62, 93, 18, 72, 83, 95, 13, 21, 27, 28, 80, 43, 68, 59, 94, 60, 99, 56, 92, 54, 25, 75, 7, 90, 50, 35, 11, 84, 17, 40),  # noqa: E501
        ),
        (
            [i for i in range(12)],
            b"&P\x18'\x91\xf6\x8f\xc8;<\xb8\x8f\x1d\x92?\xad4\xb5\xb8\x0b\xca\x8a'\x8e\xae'\xcf7\xa3(\xb2\x8d",  # noqa: E501
            (7, 3, 2, 5, 11, 9, 1, 0, 4, 6, 10, 8),

        )
    ],
)
def test_shuffle_consistent(values, seed, expect):
    assert shuffle(values, seed) == expect


def test_shuffle_out_of_bound():
    values = [i for i in range(2**24 + 1)]
    with pytest.raises(ValueError):
        shuffle(values, b'hello')
