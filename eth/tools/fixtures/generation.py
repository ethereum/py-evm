import hashlib
import os

from cytoolz import (
    curry,
    identity,
)

from .loading import (
    find_fixtures,
    find_fixture_files,
)


#
# Pytest fixture generation
#
def idfn(fixture_params):
    """
    Function for pytest to produce uniform names for fixtures.
    """
    return ":".join((str(item) for item in fixture_params))


def get_fixtures_file_hash(all_fixture_paths):
    """
    Returns the MD5 hash of the fixture files.  Used for cache busting.
    """
    hasher = hashlib.md5()
    for fixture_path in sorted(all_fixture_paths):
        with open(fixture_path, 'rb') as fixture_file:
            hasher.update(fixture_file.read())
    return hasher.hexdigest()


@curry
def generate_fixture_tests(metafunc,
                           base_fixture_path,
                           filter_fn=identity,
                           preprocess_fn=identity):
    """
    Helper function for use with `pytest_generate_tests` which will use the
    pytest caching facilities to reduce the load time for fixture tests.

    - `metafunc` is the parameter from `pytest_generate_tests`
    - `base_fixture_path` is the base path that fixture files will be collected from.
    - `filter_fn` handles ignoring or marking the various fixtures.  See `filter_fixtures`.
    - `preprocess_fn` handles any preprocessing that should be done on the raw
       fixtures (such as expanding the statetest fixtures to be multiple tests for
       each fork.
    """
    fixture_namespace = os.path.basename(base_fixture_path)

    if 'fixture_data' in metafunc.fixturenames:
        all_fixture_paths = find_fixture_files(base_fixture_path)
        current_file_hash = get_fixtures_file_hash(all_fixture_paths)

        data_cache_key = 'pyevm/statetest/fixtures/{0}/data'.format(fixture_namespace)
        file_hash_cache_key = 'pyevm/statetest/fixtures/{0}/data-hash'.format(fixture_namespace)

        cached_file_hash = metafunc.config.cache.get(file_hash_cache_key, None)
        cached_fixture_data = metafunc.config.cache.get(data_cache_key, None)

        bust_cache = any((
            cached_file_hash is None,
            cached_fixture_data is None,
            cached_file_hash != current_file_hash,
        ))

        if bust_cache:
            all_fixtures = find_fixtures(base_fixture_path)

            metafunc.config.cache.set(data_cache_key, all_fixtures)
            metafunc.config.cache.set(file_hash_cache_key, current_file_hash)
        else:
            all_fixtures = cached_fixture_data

        if not len(all_fixtures):
            raise AssertionError(
                "Suspiciously found zero fixtures: {0}".format(base_fixture_path)
            )

        filtered_fixtures = filter_fn(preprocess_fn(all_fixtures))

        metafunc.parametrize('fixture_data', filtered_fixtures, ids=idfn)
