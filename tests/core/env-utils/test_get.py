import datetime
import pytest

from evm.utils.env import (
    get,
)

try:
    import iso8601  # NOQA
    iso8601_available = True
except ImportError:
    iso8601_available = False


@pytest.mark.parametrize(
    'type,expected',
    (
        ('int', 42),
        (int, 42),

        ('bool', False),
        (bool, True),

        ('string', 'ozymandias'),
        (str, 'hannibal'),

        ('timestamp', datetime.time(11, 59)),
        (datetime.time, datetime.time(11, 59)),

        ('float', 42.0),
        (float, 42.0),
    )
)
def test_get_mapping(type, expected):
    actual = get('ENV_VARIABLE', default=expected, type=type)
    assert actual == expected


@pytest.mark.parametrize(
    'type,default,expected',
    (
        ('list', '1,2,3', ['1', '2', '3']),
        (list, '3,2,1', ['3', '2', '1']),
    )
)
def test_get_mapping_for_lists(type, default, expected):
    actual = get('ENV_VARIABLE', default=default, type=type)
    assert actual == expected


@pytest.mark.skipif(not iso8601_available, reason="iso8601 not available")
@pytest.mark.parametrize(
    'type,expected',
    (
        ('datetime', datetime.datetime(1999, 12, 31, 11, 59)),
        (datetime.datetime, datetime.datetime(1999, 12, 31, 11, 59)),
    )
)
def test_get_mapping_for_iso8601(type, expected):
    actual = get('ENV_VARIABLE', default=expected, type=type)
    assert actual == expected
