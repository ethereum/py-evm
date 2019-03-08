import pytest

from eth_utils import (
    ValidationError,
)

from eth2.beacon._utils.random import (
    get_permuted_index,
    shuffle,
)


def slow_shuffle(items, seed, shuffle_round_count):
    length = len(items)
    return tuple(
        [
            items[get_permuted_index(i, length, seed, shuffle_round_count)]
            for i in range(length)
        ]
    )


@pytest.mark.parametrize(
    (
        'values',
        'seed',
        'shuffle_round_count',
    ),
    [
        (
            tuple(range(12)),
            b'\x23' * 32,
            90,
        ),
        (
            tuple(range(2**6))[10:],
            b'\x67' * 32,
            20,
        ),
    ],
)
def test_shuffle_consistent(values, seed, shuffle_round_count):
    expect = slow_shuffle(values, seed, shuffle_round_count)
    assert shuffle(values, seed, shuffle_round_count) == expect


def test_get_permuted_index_invalid(shuffle_round_count):
    with pytest.raises(ValidationError):
        get_permuted_index(2, 2, b'\x12' * 32, shuffle_round_count)
