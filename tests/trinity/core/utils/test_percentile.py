from trinity.utils.percentile import Percentile
import random


def test_percentile_basics():
    percentile = Percentile(percentile=0.5, window_size=5)
    percentile.update(5)
    percentile.update(4)
    percentile.update(6)
    percentile.update(3)
    percentile.update(7)

    assert percentile.num_above == 0
    assert percentile.num_below == 0
    assert percentile.window == [3, 4, 5, 6, 7]

    percentile.update(5.5)

    assert percentile.num_above == 1
    assert percentile.num_below == 0
    assert percentile.window == [3, 4, 5, 5.5, 6]

    percentile.update(4.5)
    percentile.update(4.6)

    assert percentile.num_above == 2
    assert percentile.num_below == 1
    assert percentile.window == [4, 4.5, 4.6, 5, 5.5]

    percentile.update(1)

    assert percentile.num_above == 2
    assert percentile.num_below == 2
    assert percentile.window == [4, 4.5, 4.6, 5, 5.5]


def test_percentile_with_random():
    percentile = Percentile(percentile=0.9, window_size=50)
    for _ in range(1000):
        percentile.update(random.random() * 10)

    value = percentile.value
    assert abs(value - 9) < 0.5
