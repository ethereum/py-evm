import os
import pytest
import time
import datetime


from evm.utils.env import (
    env_timestamp,
)

try:
    import iso8601  # NOQA
    iso8601_available = True
except ImportError:
    iso8601_available = False


def to_timestamp(when):
    return time.mktime(when.timetuple()) + when.microsecond / 1e6


def assert_datetimes_almost_equal(w1, w2, delta=datetime.timedelta(microseconds=1)):
    assert abs(w1.replace(tzinfo=None) - w2.replace(tzinfo=None)) <= delta


def test_sanity_check_to_timestamp():
    """
    Sanity check that the from_timestamp helper works as expected
    """
    when_in = datetime.datetime.now()
    timestamp = to_timestamp(when_in)
    when_out = datetime.datetime.fromtimestamp(timestamp)

    assert_datetimes_almost_equal(when_in, when_out)


def test_env_timestamp_required_and_default_are_mutually_exclusive():
    """
    test the mutual exclusivity of the `required` and `default` keywords
    """
    assert 'TEST_DATETIME_ENV_VARIABLE' not in os.environ

    with pytest.raises(ValueError):
        env_timestamp('TEST_DATETIME_ENV_VARIABLE', required=True, default='some-default')


def test_with_no_default():
    assert 'TEST_DATETIME_ENV_VARIABLE' not in os.environ

    with pytest.raises(ValueError):
        env_timestamp('TEST_DATETIME_ENV_VARIABLE')


def test_with_timestamp(monkeypatch):
    when_in = datetime.datetime.now()
    timestamp = to_timestamp(when_in)

    monkeypatch.setenv(
        'TEST_DATETIME_ENV_VARIABLE', repr(timestamp),
    )

    when_out = env_timestamp('TEST_DATETIME_ENV_VARIABLE')

    assert_datetimes_almost_equal(when_in, when_out)


def test_with_utc_timestamp(monkeypatch):
    when_in = datetime.datetime.utcnow()
    timestamp = to_timestamp(when_in)

    monkeypatch.setenv(
        'TEST_DATETIME_ENV_VARIABLE', repr(timestamp),
    )

    when_out = env_timestamp('TEST_DATETIME_ENV_VARIABLE')

    assert_datetimes_almost_equal(when_in, when_out)
