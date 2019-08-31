from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence, Tuple, Type

from eth_utils import to_tuple
import eth_utils.toolz as toolz

from eth2.beacon.tools.fixtures.config_types import ConfigType
from eth2.beacon.tools.fixtures.fork_types import ForkType
from eth2.beacon.tools.fixtures.format_type import FormatType, SSZType, YAMLType
from eth2.beacon.tools.fixtures.loading import load_config_at_path
from eth2.beacon.tools.fixtures.test_case import TestCase
from eth2.beacon.tools.fixtures.test_handler import Input, Output, TestHandler
from eth2.beacon.tools.fixtures.test_part import TestPart
from eth2.beacon.tools.fixtures.test_suite import TestSuite
from eth2.beacon.tools.fixtures.test_types import HandlerType, TestType
from eth2.beacon.tools.misc.ssz_vector import override_lengths
from eth2.configs import Eth2Config

# NOTE: if the tests_root_path keeps changing, can turn into
# a ``pytest.config.Option`` and supply from the command line.
TESTS_ROOT_PATH = Path("eth2-fixtures")
TESTS_PATH = Path("tests")


@dataclass
class TestCaseDescriptor:
    name: str
    parts: Tuple[Path, ...]


@dataclass
class TestSuiteDescriptor:
    name: str
    test_case_descriptors: Tuple[TestCaseDescriptor, ...]


def _build_test_handler_path(
    tests_path: Path,
    test_type: TestType[HandlerType],
    test_handler: TestHandler[Input, Output],
    config_type: ConfigType,
    fork_type: ForkType,
) -> Path:
    return (
        tests_path
        / Path(config_type.name)
        / Path(fork_type.name)
        / Path(test_type.name)
        / Path(test_handler.name)
    )


def _format_type_for(file_type: str) -> Type[FormatType]:
    if file_type == ".yaml":
        return YAMLType
    elif file_type == ".ssz":
        return SSZType
    else:
        raise AssertionError(
            f"File type `{file_type}` found in fixture data is not currently supported."
        )


def _group_paths_by_name(path: Path) -> str:
    return path.name.replace(path.suffix, "")


def _map_to_format_type(
    items: Tuple[str, Sequence[Path]]
) -> Tuple[Type[FormatType], Path]:
    suffix, paths = items
    # sanity check
    assert len(paths) == 1

    return (_format_type_for(suffix), paths[0])


def _mk_test_part(paths: Sequence[Path]) -> TestPart:
    paths_by_suffix = toolz.groupby(lambda path: path.suffix, paths)
    return TestPart(toolz.itemmap(_map_to_format_type, paths_by_suffix))


def _load_parts(parts: Iterable[Path]) -> Dict[str, TestPart]:
    parts_by_name = toolz.groupby(_group_paths_by_name, parts)
    return toolz.valmap(_mk_test_part, parts_by_name)


@to_tuple
def _parse_test_cases(
    config: Optional[Eth2Config],
    test_handler: TestHandler[Input, Output],
    test_case_descriptors: Iterable[TestCaseDescriptor],
) -> Iterable[TestCase]:
    for descriptor in test_case_descriptors:
        test_case_parts = _load_parts(descriptor.parts)
        yield TestCase(descriptor.name, test_handler, test_case_parts, config)


def _load_test_case(test_case_path: Path) -> TestCaseDescriptor:
    parts = tuple(part_path for part_path in test_case_path.iterdir())
    return TestCaseDescriptor(test_case_path.name, parts)


@to_tuple
def _discover_test_suite_from(test_handler_path: Path) -> Iterable[TestSuiteDescriptor]:
    for test_suite in test_handler_path.iterdir():
        test_case_descriptors = tuple(
            _load_test_case(test_case_path) for test_case_path in test_suite.iterdir()
        )
        yield TestSuiteDescriptor(test_suite.name, test_case_descriptors)


@to_tuple
def _load_and_parse_test_suites(
    tests_path: Path,
    test_type: TestType[HandlerType],
    test_handler: TestHandler[Input, Output],
    config_type: ConfigType,
    fork_type: ForkType,
) -> Iterable[TestSuite]:
    test_handler_path = _build_test_handler_path(
        tests_path, test_type, test_handler, config_type, fork_type
    )

    test_suite_descriptors = _discover_test_suite_from(test_handler_path)

    if config_type.has_config():
        config_path = tests_path / Path(config_type.name) / Path(config_type.path)
        config = load_config_at_path(config_path)
        override_lengths(config)
    else:
        config = None

    for descriptor in test_suite_descriptors:
        yield TestSuite(
            descriptor.name,
            _parse_test_cases(config, test_handler, descriptor.test_case_descriptors),
        )


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


def parse_test_suites(
    test_type: TestType[HandlerType],
    test_handler: TestHandler[Input, Output],
    config_type: ConfigType,
    fork_type: ForkType,
) -> Tuple[TestSuite, ...]:
    """
    Find all of the test suites (including their respective test cases) given a fixed
    ``test_type``, ``test_handler``, ``config_type``, ``fork_type`` and ``format_type``.

    This search directly corresponds to finding subtrees of the file hierarchy
    under particular paths fixed by the function arguments.
    """
    project_root_dir = _find_project_root_dir(TESTS_ROOT_PATH)
    tests_path = project_root_dir / TESTS_ROOT_PATH / TESTS_PATH
    return _load_and_parse_test_suites(
        tests_path, test_type, test_handler, config_type, fork_type
    )
