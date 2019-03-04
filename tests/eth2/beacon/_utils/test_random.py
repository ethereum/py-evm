import pytest

from eth2.beacon._utils.random import (
    shuffle,
)


@pytest.mark.parametrize(
    (
        'values,seed,expect'
    ),
    [
        (
            tuple(range(12)),
            b'\x23' * 32,
            (8, 3, 9, 0, 1, 11, 2, 4, 6, 7, 10, 5),
        ),
    ],
)
def test_shuffle_consistent(values, seed, expect):
    assert shuffle(values, seed) == expect


def test_shuffle_out_of_bound():
    values = [i for i in range(2**24 + 1)]
    with pytest.raises(ValueError):
        shuffle(values, b'hello')
