from pathlib import Path
from typing import Any, Dict, Generator, Optional, Sequence

from eth2.beacon.tools.fixtures.config_types import ConfigType
from eth2.beacon.tools.fixtures.loading import load_config_at_path, load_test_suite_at
from eth2.beacon.tools.fixtures.test_case import TestCase
from eth2.beacon.tools.fixtures.test_handler import Input, Output, TestHandler
from eth2.beacon.tools.fixtures.test_types import HandlerType, TestType
from eth2.beacon.tools.misc.ssz_vector import override_lengths
from eth2.configs import Eth2Config

# NOTE: if the tests_root_path keeps changing, can turn into
# a ``pytest.config.Option`` and supply from the command line.
TESTS_ROOT_PATH = Path("eth2-fixtures")
TESTS_PATH = Path("tests")

TestSuite = Generator[TestCase, None, None]


def _build_test_suite_path(
    tests_root_path: Path,
    test_type: TestType[HandlerType],
    test_handler: TestHandler[Input, Output],
    config_type: Optional[ConfigType],
) -> Path:
    return test_type.build_path(tests_root_path, test_handler, config_type)


def _parse_test_cases(
    config: Eth2Config,
    test_handler: TestHandler[Input, Output],
    test_cases: Sequence[Dict[str, Any]],
) -> TestSuite:
    for index, test_case in enumerate(test_cases):
        yield TestCase(index, test_case, test_handler, config)


def _load_test_suite(
    tests_root_path: Path,
    test_type: TestType[HandlerType],
    test_handler: TestHandler[Input, Output],
    config_type: Optional[ConfigType],
    config: Optional[Eth2Config],
) -> TestSuite:
    test_suite_path = _build_test_suite_path(
        tests_root_path, test_type, test_handler, config_type
    )

    test_suite_data = load_test_suite_at(test_suite_path)

    return _parse_test_cases(config, test_handler, test_suite_data["test_cases"])


class DirectoryNotFoundException(Exception):
    pass


def _search_for_dir(target_dir: Path, p: Path) -> Path:
    for child in p.iterdir():
        if not child.is_dir():
            continue
        if child.name == target_dir.name:
            return child
    raise DirectoryNotFoundException()


def _find_project_root_dir(target: Path) -> Path:
    """
    Search the file tree for a path with a child directory equal to ``target``.
    """
    p = Path(".").resolve()
    for _ in range(1000):
        try:
            candidate = _search_for_dir(target, p)
            return candidate.parent
        except DirectoryNotFoundException:
            p = p.parent
    raise DirectoryNotFoundException


def parse_test_suite(
    test_type: TestType[HandlerType],
    test_handler: TestHandler[Input, Output],
    config_type: Optional[ConfigType],
) -> TestSuite:
    project_root_dir = _find_project_root_dir(TESTS_ROOT_PATH)
    tests_path = project_root_dir / TESTS_ROOT_PATH / TESTS_PATH
    if config_type:
        config_path = project_root_dir / config_type.path
        config = load_config_at_path(config_path)
        override_lengths(config)
    else:
        config = None

    return _load_test_suite(tests_path, test_type, test_handler, config_type, config)
