import os

import pytest

from eth._utils.env import (
    env_float,
)


@pytest.mark.parametrize(
    "env_value,expected",
    (
        ("1.01", 1.01),
        ("123.0", 123.0),
        ("-123.99", -123.99),
    ),
)
def test_env_float_not_required_with_no_default(monkeypatch, env_value, expected):
    """
    Test that when the environment variable is present that it is parsed to a float.
    """
    monkeypatch.setenv("TEST_FLOAT_ENV_VARIABLE", env_value)

    actual = env_float("TEST_FLOAT_ENV_VARIABLE")
    assert actual == expected


def test_env_float_not_required_and_not_set():
    """
    Test that when the env variable is not set and not required it raises a
    ValueError
    """
    # sanity check
    assert "TEST_FLOAT_ENV_VARIABLE" not in os.environ

    with pytest.raises(ValueError):
        env_float("TEST_FLOAT_ENV_VARIABLE")


def test_env_float_when_missing_and_required_is_error():
    """
    Test that when the env variable is not set and is required, it raises an
    error.
    """
    # sanity check
    assert "TEST_FLOAT_ENV_VARIABLE" not in os.environ

    with pytest.raises(KeyError):
        env_float("TEST_FLOAT_ENV_VARIABLE", required=True)
