from pathlib import Path

from eth2.beacon.tools.fixtures.config_types import ConfigType
from eth2.beacon.tools.fixtures.test_handler import TestHandler
from eth2.beacon.tools.fixtures.loading import load_config_at_path, load_test_suite_at
from eth2.beacon.tools.fixtures.test_types import TestType
from eth2.beacon.tools.fixtures.test_suite import TestSuite
from eth2.beacon.tools.misc.ssz_vector import (
    override_lengths,
)

from eth2.configs import Eth2Config


# NOTE: if the tests_root_path keeps changing, can turn into
# a ``pytest.config.Option`` and supply from the command line.
TESTS_ROOT_PATH = Path("eth2-fixtures")
TESTS_PATH = Path("tests")


def _build_test_suite_path(tests_root_path: Path,
                           test_type: TestType,
                           test_handler: TestHandler,
                           config_type: ConfigType) -> Path:
    return test_type.build_path(
        tests_root_path,
        test_handler,
        config_type,
    )


def _load_test_suite(tests_root_path: Path,
                     test_type: TestType,
                     test_handler: TestHandler,
                     config_type: ConfigType,
                     config: Eth2Config) -> TestSuite:
    test_suite_path = _build_test_suite_path(
        tests_root_path,
        test_type,
        test_handler,
        config_type,
    )

    test_suite_data = load_test_suite_at(test_suite_path)

    return TestSuite(config, test_handler, test_suite_data)


def _search_for_dir(target_dir, p):
    for child in p.iterdir():
        if not child.is_dir():
            continue
        if child.name == target_dir.name:
            return child
    return None


def _find_project_root_dir(target: Path) -> Path:
    """
    Search the file tree for a path with a child directory equal to ``target``.
    """
    p = Path('.').resolve()
    for _ in range(1000):
        candidate = _search_for_dir(target, p)
        if candidate:
            return candidate.parent
        p = p.parent


def parse_test_suite(test_type: TestType,
                     test_handler: TestHandler,
                     config_type: ConfigType) -> TestSuite:
    project_root_dir = _find_project_root_dir(TESTS_ROOT_PATH)
    tests_path = project_root_dir / TESTS_ROOT_PATH / TESTS_PATH
    config_path = project_root_dir / config_type.path
    config = load_config_at_path(config_path)
    override_lengths(config)

    return _load_test_suite(
        tests_path,
        test_type,
        test_handler,
        config_type,
        config,
    )
