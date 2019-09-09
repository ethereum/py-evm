import pytest

from p2p.stats.stddev import StandardDeviation


@pytest.mark.parametrize(
    "data,expected",
    (
        ((4, 2, 5, 8, 6), 2.23606),
        ((1.5, 1.8, 7, 1.2, 1.35), 2.4863),
        ((2, 2, 2, 2, 2), 0),
        ((1, 3, 5, 7, 9), 3.1622),
        ((100, 200, 300, 400, 500, 1, 3, 5, 7, 9), 3.1622),
    ),
)
def test_standard_deviation(data, expected):
    stddev = StandardDeviation(window_size=5)

    for value in data:
        stddev.update(value)

    assert abs(stddev.value - expected) < 0.01
