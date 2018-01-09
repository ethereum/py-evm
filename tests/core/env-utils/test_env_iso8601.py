import os
import pytest

import datetime

from evm.utils.env import (
    env_iso8601,
)

try:
    import iso8601  # NOQA
    iso8601_available = True
except ImportError:
    iso8601_available = False


def assert_datetimes_almost_equal(w1, w2, delta=datetime.timedelta(microseconds=1)):
    assert abs(w1.replace(tzinfo=None) - w2.replace(tzinfo=None)) <= delta


@pytest.mark.skipif(not iso8601_available, reason="iso8601 not available")
def test_env_iso8601_required_and_default_are_mutually_exclusive():
    """
    test the mutual exclusivity of the `required` and `default` keywords
    """
    assert 'TEST_DATETIME_ENV_VARIABLE' not in os.environ

    with pytest.raises(ValueError):
        env_iso8601('TEST_DATETIME_ENV_VARIABLE', required=True, default='some-default')


@pytest.mark.skipif(not iso8601_available, reason="iso8601 not available")
def test_with_no_default():
    assert 'TEST_DATETIME_ENV_VARIABLE' not in os.environ

    with pytest.raises(ValueError):
        env_iso8601('TEST_DATETIME_ENV_VARIABLE')


@pytest.mark.skipif(iso8601_available, reason="iso8601 available")
def test_iso8601_with_library_not_installed(monkeypatch):
    when_in = datetime.datetime.utcnow()

    monkeypatch.setenv(
        'TEST_DATETIME_ENV_VARIABLE', when_in.isoformat(),
    )

    with pytest.raises(ImportError):
        env_iso8601('TEST_DATETIME_ENV_VARIABLE')


@pytest.mark.skipif(not iso8601_available, reason="iso8601 not available")
def test_iso8601_parsing(monkeypatch):
    when_in = datetime.datetime.utcnow()

    monkeypatch.setenv(
        'TEST_DATETIME_ENV_VARIABLE', when_in.isoformat(),
    )

    when_out = env_iso8601('TEST_DATETIME_ENV_VARIABLE')

    assert_datetimes_almost_equal(when_in, when_out)
