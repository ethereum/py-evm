import pytest

from eth._utils.env import (
    get,
)


@pytest.mark.parametrize(
    "type,expected",
    (
        ("int", 42),
        (int, 42),
        ("bool", False),
        (bool, True),
        ("string", "ozymandias"),
        (str, "hannibal"),
        ("float", 42.0),
        (float, 42.0),
    ),
)
def test_get_mapping(type, expected):
    actual = get("ENV_VARIABLE", default=expected, type=type)
    assert actual == expected


@pytest.mark.parametrize(
    "type,default,expected",
    (
        ("list", "1,2,3", ["1", "2", "3"]),
        (list, "3,2,1", ["3", "2", "1"]),
    ),
)
def test_get_mapping_for_lists(type, default, expected):
    actual = get("ENV_VARIABLE", default=default, type=type)
    assert actual == expected
