import hashlib
from typing import (
    Any,
    Callable,
    Iterable,
)

from eth_utils.toolz import (
    curry,
    identity,
)

from .loading import (
    find_fixtures,
)


#
# Pytest fixture generation
#
def idfn(fixture_params: Iterable[Any]) -> str:
    """
    Function for pytest to produce uniform names for fixtures.
    """
    try:
        return ":".join(str(item) for item in fixture_params)
    except TypeError:
        # In case params are not iterable for some reason...
        return str(fixture_params)


def get_fixtures_file_hash(all_fixture_paths: Iterable[str]) -> str:
    """
    Returns the MD5 hash of the fixture files.  Used for cache busting.
    """
    hasher = hashlib.md5()
    for fixture_path in sorted(all_fixture_paths):
        with open(fixture_path, "rb") as fixture_file:
            hasher.update(fixture_file.read())
    return hasher.hexdigest()


@curry
def generate_fixture_tests(
    metafunc: Any,
    base_fixture_path: str,
    filter_fn: Callable[..., Any] = identity,
    preprocess_fn: Callable[..., Any] = identity,
) -> None:
    """
    Helper function for use with `pytest_generate_tests` which will use the
    pytest caching facilities to reduce the load time for fixture tests.

    - `metafunc` is the parameter from `pytest_generate_tests`
    - `base_fixture_path` is the base path that fixture files will be collected from.
    - `filter_fn` handles ignoring or marking the various fixtures.
       See `filter_fixtures`.
    - `preprocess_fn` handles any preprocessing that should be done on the raw
       fixtures (such as expanding the statetest fixtures to be multiple tests for
       each fork.
    """
    if "fixture_data" in metafunc.fixturenames:
        all_fixtures = find_fixtures(base_fixture_path)

        if not all_fixtures:
            raise AssertionError(
                f"Suspiciously found zero fixtures: {base_fixture_path}"
            )

        filtered_fixtures = filter_fn(preprocess_fn(all_fixtures))

        metafunc.parametrize("fixture_data", filtered_fixtures, ids=idfn)
