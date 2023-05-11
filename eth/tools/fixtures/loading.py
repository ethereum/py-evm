import functools
import json
import os
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Tuple,
)

from eth_utils import (
    to_tuple,
)
from eth_utils.toolz import (
    curry,
    identity,
)

from ._utils import (
    recursive_find_files,
    require_pytest,
)


#
# Filesystem fixture loading.
#
def find_fixture_files(fixtures_base_dir: str) -> Iterable[str]:
    all_fixture_paths = recursive_find_files(fixtures_base_dir, "*.json")
    return all_fixture_paths


@to_tuple
def find_fixtures(fixtures_base_dir: str) -> Iterable[Tuple[str, str]]:
    """
    Finds all of the (fixture_path, fixture_key) pairs for a given path under
    the JSON test fixtures directory.
    """
    all_fixture_paths = find_fixture_files(fixtures_base_dir)

    for fixture_path in sorted(all_fixture_paths):
        with open(fixture_path) as fixture_file:
            fixtures = json.load(fixture_file)

        for fixture_key in sorted(fixtures.keys()):
            yield (fixture_path, fixture_key)


# we use an LRU cache on this function so that we can sort the tests such that
# all fixtures from the same file are executed sequentially allowing us to keep
# a small rolling cache of the loaded fixture files.
@functools.lru_cache(maxsize=16)
def load_json_fixture(fixture_path: str) -> Dict[str, Any]:
    """
    Loads a fixture file, caching the most recent files it loaded.
    """
    with open(fixture_path) as fixture_file:
        file_fixtures = json.load(fixture_file)
    return file_fixtures


def load_fixture(
    fixture_path: str, fixture_key: str, normalize_fn: Callable[..., Any] = identity
) -> Dict[str, Any]:
    """
    Loads a specific fixture from a fixture file, optionally passing it through
    a normalization function.
    """
    file_fixtures = load_json_fixture(fixture_path)
    fixture = normalize_fn(file_fixtures[fixture_key])
    return fixture


@require_pytest
@curry
def filter_fixtures(
    all_fixtures: Iterable[Any],
    fixtures_base_dir: str,
    mark_fn: Callable[[str, str], bool] = None,
    ignore_fn: Callable[..., bool] = None,
) -> Any:
    """
    Helper function for filtering test fixtures.

    - `fixtures_base_dir` should be the base dir that the fixtures were collected from.
    - `mark_fn` should be a func which either returns `None` or a `pytest.mark` object.
    - `ignore_fn` should be a function which returns `True` for any fixture
       which should be ignored.
    """
    import pytest  # noqa: F401

    for fixture_data in all_fixtures:
        fixture_path = fixture_data[0]
        fixture_relpath = os.path.relpath(fixture_path, fixtures_base_dir)

        if ignore_fn:
            if ignore_fn(fixture_relpath, *fixture_data[1:]):
                continue

        if mark_fn is not None:
            mark = mark_fn(fixture_relpath, *fixture_data[1:])
            if mark:
                yield pytest.param(
                    (fixture_path, *fixture_data[1:]),
                    marks=mark,
                )
                continue

        yield fixture_data
