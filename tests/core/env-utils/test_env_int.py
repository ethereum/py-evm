import os

import pytest

from eth._utils.env import (
    env_int,
)


@pytest.mark.parametrize(
    "env_value,expected",
    (
        ("1", 1),
        ("123", 123),
        ("-123", -123),
    ),
)
def test_env_int_not_required_with_no_default(monkeypatch, env_value, expected):
    """
    Test that when the environment variable is present that it is parsed to a int.
    """
    monkeypatch.setenv("TEST_INT_ENV_VARIABLE", env_value)

    actual = env_int("TEST_INT_ENV_VARIABLE")
    assert actual == expected


def test_env_int_not_required_and_not_set():
    """
    Test that when the env variable is not set and not required it raises a
    ValueError
    """
    # sanity check
    assert "TEST_INT_ENV_VARIABLE" not in os.environ

    with pytest.raises(ValueError):
        env_int("TEST_INT_ENV_VARIABLE")


def test_env_int_when_missing_and_required_is_error():
    """
    Test that when the env variable is not set and is required, it raises an
    error.
    """
    # sanity check
    assert "TEST_INT_ENV_VARIABLE" not in os.environ

    with pytest.raises(KeyError):
        env_int("TEST_INT_ENV_VARIABLE", required=True)


@pytest.mark.parametrize(
    "default,expected",
    (
        (1, 1),
        ("1", 1),
        ("-1", -1),
        (-1, -1),
    ),
)
def test_env_int_when_missing_and_default_provided(default, expected):
    """
    Test that when the env variable is not set and a default is provided, the
    default is used.
    """
    assert "TEST_INT_ENV_VARIABLE" not in os.environ

    actual = env_int("TEST_INT_ENV_VARIABLE", default=default)
    assert actual == expected


def test_that_required_and_default_are_mutually_exclusive():
    """
    Test that when `required` and `default` are both set, raises a ValueError.
    """
    with pytest.raises(ValueError):
        env_int("TEST_INT_ENV_VARIABLE", required=True, default=1)
