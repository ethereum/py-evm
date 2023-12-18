from collections.abc import (
    Mapping,
)
import itertools
from typing import (
    Any,
    Dict,
    Sequence,
)

from eth_utils.toolz import (
    merge_with,
)


def merge_if_dicts(values: Sequence[Dict[Any, Any]]) -> Any:
    if all(isinstance(item, Mapping) for item in values):
        return merge_with(merge_if_dicts, *values)
    else:
        return values[-1]


def deep_merge(*dicts: Dict[Any, Any]) -> Dict[Any, Any]:
    return merge_with(merge_if_dicts, *dicts)


def is_cleanly_mergable(*dicts: Dict[Any, Any]) -> bool:
    """
    Check that nothing will be overwritten when
    dictionaries are merged using `deep_merge`.

    Examples
    --------

        >>> is_cleanly_mergable({"a": 1}, {"b": 2}, {"c": 3})
        True
        >>> is_cleanly_mergable({"a": 1}, {"b": 2}, {"a": 0, c": 3})
        False
        >>> is_cleanly_mergable({"a": 1, "b": {"ba": 2}}, {"c": 3, {"b": {"bb": 4}})
        True
        >>> is_cleanly_mergable({"a": 1, "b": {"ba": 2}}, {"b": {"ba": 4}})
        False

    """
    if len(dicts) <= 1:
        return True
    elif len(dicts) == 2:
        if not all(isinstance(d, Mapping) for d in dicts):
            return False
        else:
            shared_keys = set(dicts[0].keys()) & set(dicts[1].keys())
            return all(
                is_cleanly_mergable(dicts[0][key], dicts[1][key]) for key in shared_keys
            )
    else:
        dict_combinations = itertools.combinations(dicts, 2)
        return all(
            is_cleanly_mergable(*combination) for combination in dict_combinations
        )
