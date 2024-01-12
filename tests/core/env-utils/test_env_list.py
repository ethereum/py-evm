import os

import pytest

from eth._utils.env import (
    env_list,
)


def test_env_list_with_stock_usage(monkeypatch):
    """
    Test that when the environment variable is present that is is split on
    commas (by default) and returned as a list.
    """
    monkeypatch.setenv("TEST_LIST_ENV_VARIABLE", "a,b,c")

    actual = env_list("TEST_LIST_ENV_VARIABLE")
    assert actual == ["a", "b", "c"]


def test_env_list_removes_whitespace(monkeypatch):
    """
    Test that extra whitespace is removed from list values.
    """
    monkeypatch.setenv("TEST_LIST_ENV_VARIABLE", "a, b, c")

    actual = env_list("TEST_LIST_ENV_VARIABLE")
    assert actual == ["a", "b", "c"]


def test_env_list_with_custom_separator(monkeypatch):
    """
    Test that when the environment variable is missing and a default is
    provided, the default is retured.
    """
    monkeypatch.setenv("TEST_LIST_ENV_VARIABLE", "a:b:c")

    actual = env_list("TEST_LIST_ENV_VARIABLE", separator=":")
    assert actual == ["a", "b", "c"]


def test_env_list_with_empty_list(monkeypatch):
    """
    Test that when the environment variable is missing and a default is
    provided, the default is used.
    """
    monkeypatch.setenv("TEST_LIST_ENV_VARIABLE", "")

    actual = env_list("TEST_LIST_ENV_VARIABLE")
    assert actual == []


def test_env_list_with_default_value():
    """
    Test that when the environment variable is missing and a default is
    provided, the default is used.
    """
    # sanity check
    assert "TEST_LIST_ENV_VARIABLE" not in os.environ

    actual = env_list("TEST_LIST_ENV_VARIABLE", default="a,b,c")
    assert actual == ["a", "b", "c"]


def test_env_list_with_required_raises_when_not_present():
    # sanity check
    assert "TEST_LIST_ENV_VARIABLE" not in os.environ

    with pytest.raises(KeyError):
        env_list("TEST_LIST_ENV_VARIABLE", required=True)


def test_env_list_with_required_and_default_is_error():
    with pytest.raises(ValueError):
        env_list("TEST_LIST_ENV_VARIABLE", required=True, default="a,b,c")
