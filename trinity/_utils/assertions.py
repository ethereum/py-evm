from typing import Any

from eth_utils import is_list_like


def assert_type_equality(left: Any, right: Any) -> None:
    assert type(left) is type(right)
    if is_list_like(left):
        assert is_list_like(right)
        assert len(left) == len(right)
        for left_item, right_item in zip(left, right):
            assert_type_equality(left_item, right_item)
