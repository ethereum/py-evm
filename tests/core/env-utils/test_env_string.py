import os

import pytest

from eth._utils.env import (
    env_string,
)


def test_env_string_with_basic_usage(monkeypatch):
    """
    Test that when the environment variable is present that it is returned as a
    string.
    """
    monkeypatch.setenv("TEST_BOOLEAN_ENV_VARIABLE", "test-value")

    actual = env_string("TEST_BOOLEAN_ENV_VARIABLE")
    assert actual == "test-value"


def test_env_string_with_default_value(monkeypatch):
    """
    Test that when the environment variable is missing and a default is
    provided, the default is retured.
    """
    assert "TEST_BOOLEAN_ENV_VARIABLE" not in os.environ

    actual = env_string("TEST_BOOLEAN_ENV_VARIABLE", default="test-value")
    assert actual == "test-value"


def test_env_string_with_required():
    """
    Test that when the environment variable is missing and a default is
    provided, the default is retured.
    """
    assert "TEST_BOOLEAN_ENV_VARIABLE" not in os.environ

    with pytest.raises(KeyError):
        env_string("TEST_BOOLEAN_ENV_VARIABLE", required=True)


def test_env_string_with_required_and_default_is_error():
    with pytest.raises(ValueError):
        env_string("TEST_BOOLEAN_ENV_VARIABLE", required=True, default="test-value")
