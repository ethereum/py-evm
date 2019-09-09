import pytest

from p2p.stats.percentile import Percentile


@pytest.mark.parametrize(
    'data,percentile,window_size,expected',
    (
        (range(6), 0.2, 6, 1),
        (range(11), 0.4, 11, 4),
        (range(11), 0.2, 6, 6),
    ),
)
def test_percentile_class(data, percentile, window_size, expected):
    percentile = Percentile(percentile=percentile, window_size=window_size)
    for value in data:
        percentile.update(value)

    assert percentile.value == expected
