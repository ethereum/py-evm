import pytest

from trinity.utils.humanize import humanize_elapsed, humanize_hash


SECOND = 1
MINUTE = 60
HOUR = 60 * 60
DAY = 24 * HOUR
YEAR = 365 * DAY
MONTH = YEAR // 12
WEEK = 7 * DAY


@pytest.mark.parametrize(
    'seconds,expected',
    (
        (0, '0s'),
        (1, '1s'),
        (60, '1m'),
        (61, '1m1s'),
        (119, '1m59s'),
        (HOUR, '1h'),
        (HOUR + 1, '1h0m1s'),
        (HOUR + MINUTE + 1, '1h1m1s'),
        (DAY + HOUR, '1d1h'),
        (DAY + HOUR + MINUTE, '1d1h1m'),
        (DAY + MINUTE, '1d0h1m'),
        (DAY + MINUTE + 1, '1d0h1m'),
        (WEEK + DAY + HOUR, '1w1d1h'),
        (WEEK + DAY + HOUR + MINUTE, '1w1d1h'),
        (WEEK + DAY + HOUR + SECOND, '1w1d1h'),
        (MONTH + WEEK + DAY, '1m1w1d'),
        (MONTH + WEEK + DAY + HOUR, '1m1w1d'),
        (YEAR + MONTH + WEEK, '1y1m1w'),
        (YEAR + MONTH + WEEK + DAY, '1y1m1w'),
    ),
)
def test_humanize_elapsed(seconds, expected):
    actual = humanize_elapsed(seconds)
    assert actual == expected


@pytest.mark.parametrize(
    'hash32,expected',
    (
        (bytes(range(32)), '0001..1e1f'),
    )
)
def test_humanize_hash(hash32, expected):
    assert humanize_hash(hash32) == expected
