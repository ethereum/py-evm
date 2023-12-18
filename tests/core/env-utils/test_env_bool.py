import os

import pytest

from eth._utils.env import (
    env_bool,
)


@pytest.mark.parametrize(
    "env_value,expected",
    (
        ("True", True),
        ("true", True),
        ("not-a-known-value", False),
        ("False", False),
    ),
)
def test_env_bool_not_required_with_no_default(monkeypatch, env_value, expected):
    """
    Test that when the environment variable is present that it is parsed to a boolean.
    """
    monkeypatch.setenv("TEST_BOOLEAN_ENV_VARIABLE", env_value)

    actual = env_bool("TEST_BOOLEAN_ENV_VARIABLE")
    assert actual is expected


def test_env_bool_not_required_and_not_set():
    """
    Test that when the env variable is not set and not required it returns
    `None`.
    """
    # sanity check
    assert "TEST_BOOLEAN_ENV_VARIABLE" not in os.environ

    actual = env_bool("TEST_BOOLEAN_ENV_VARIABLE")
    assert actual is None


def test_env_bool_when_missing_and_required_is_error():
    """
    Test that when the env variable is not set and is required, it raises an
    error.
    """
    # sanity check
    assert "TEST_BOOLEAN_ENV_VARIABLE" not in os.environ

    with pytest.raises(KeyError):
        env_bool("TEST_BOOLEAN_ENV_VARIABLE", required=True)


@pytest.mark.parametrize(
    "default,expected",
    (
        (True, True),
        ("true", True),
        ("True", True),
        ("1", False),  # not sure if this is the correct behavior...
        (False, False),
        ("0", False),
    ),
)
def test_env_bool_when_missing_and_default_provided(default, expected):
    """
    Test that when the env variable is not set and a default is provided, the
    default is used.
    """
    assert "TEST_BOOLEAN_ENV_VARIABLE" not in os.environ

    actual = env_bool("TEST_BOOLEAN_ENV_VARIABLE", default=default)
    assert actual is expected


def test_that_required_and_default_are_mutually_exclusive():
    """
    Test that when `required` and `default` are both set, raises a ValueError.
    """
    with pytest.raises(ValueError):
        env_bool("TEST_BOOLEAN_ENV_VARIABLE", required=True, default=True)
