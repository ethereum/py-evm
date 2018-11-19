from typing import Iterator


def humanize_elapsed(seconds: int) -> str:
    return ''.join(_humanize_elapsed(seconds))


SECOND = 1
MINUTE = 60
HOUR = 60 * 60
DAY = 24 * HOUR
YEAR = 365 * DAY
MONTH = YEAR // 12
WEEK = 7 * DAY


UNITS = (
    (YEAR, 'y'),
    (MONTH, 'm'),
    (WEEK, 'w'),
    (DAY, 'd'),
    (HOUR, 'h'),
    (MINUTE, 'm'),
    (SECOND, 's'),
)


def _humanize_elapsed(seconds: int) -> Iterator[str]:
    if not seconds:
        yield '0s'

    num_display_units = 0
    remainder = seconds

    for duration, unit in UNITS:
        if not remainder:
            break
        if remainder >= duration or num_display_units:
            num = remainder // duration
            yield f"{num}{unit}"
            num_display_units += 1

        if num_display_units >= 3:
            return

        remainder %= duration
