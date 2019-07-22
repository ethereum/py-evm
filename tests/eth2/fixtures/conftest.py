import pytest

from pathlib import Path

from eth2.beacon.tools.fixtures.config_types import (
    # Mainnet,
    Minimal,
)


def _search_for_dir(target_dir, p):
    for child in p.iterdir():
        if not child.is_dir():
            continue
        if child.name == target_dir:
            return child
    return None


def _find_tests_root_dir(target_dir):
    """
    Starts from the current file and walks up the filesystem tree
    until we find a directory with name ``target_dir``.

    NOTE: assumes the ``target_dir`` is a sibling or above the current
    working directory in the filesystem tree.
    """
    p = Path('.').resolve()
    root = p.root
    while p != root:
        target = _search_for_dir(target_dir, p)
        if target:
            return target
        p = p.parent


@pytest.fixture(scope="session")
def tests_root_dir():
    return _find_tests_root_dir("eth2-fixtures")


@pytest.fixture(scope="session")
def tests_path(tests_root_dir):
    return tests_root_dir / "tests"


@pytest.fixture(scope="session")
def config_path_provider():
    # TODO update when we move config
    test_dir = Path(__file__).parent
    return lambda config_type: {
        Minimal: test_dir / "minimal.yaml",
    }[config_type]
