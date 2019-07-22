from pathlib import Path
from typing import (
    Callable,
    Iterable,
)

from eth_utils.toolz import (
    mapcat,
    partial,
)

from eth2.beacon.tools.fixtures.config_descriptor import ConfigDescriptor
from eth2.beacon.tools.fixtures.config_types import ConfigType
from eth2.beacon.tools.fixtures.handlers import Handler
from eth2.beacon.tools.fixtures.loading import load_config_at_path, load_test_case_at
from eth2.beacon.tools.fixtures.test_type import TestType
from eth2.beacon.tools.fixtures.test_case import TestCase

from eth2.configs import Eth2Config


def _find_handler_paths_for_test_type(tests_root_path: Path,
                                      test_type: TestType,
                                      handler_filter: Callable[[str], bool]) -> Iterable[Path]:
    test_type_path = tests_root_path / test_type.name()
    for entry in test_type_path.iterdir():
        if not entry.is_dir():
            continue

        handler_name = entry.name
        if handler_filter(handler_name):
            yield entry


def _find_test_suite_paths_for_handler(path: Path, config_type: ConfigType) -> Iterable[Path]:
    for entry in path.iterdir():
        if entry.is_dir():
            # NOTE: assuming no deeper nesting
            continue

        if config_type in entry.name:
            yield entry


def _load_test_cases(tests_root_path: Path,
                     test_type: TestType,
                     handler_filter: Callable[[str], bool],
                     config_type: ConfigType,
                     config: Eth2Config) -> Iterable[TestCase]:
    handler_paths = _find_handler_paths_for_test_type(
        tests_root_path,
        test_type,
        handler_filter,
    )

    test_suite_paths = mapcat(
        lambda path: _find_test_suite_paths_for_handler(path, config_type),
        handler_paths,
    )

    test_case_data = map(
        load_test_case_at,
        test_suite_paths,
    )

    return map(
        partial(test_type, config),
        test_case_data,
    )


def parse_tests(tests_root_path: Path,
                test_type: TestType,
                handler_filter: Callable[[Handler], bool],
                config_descriptor: ConfigDescriptor) -> Iterable[TestCase]:
    config = load_config_at_path(config_descriptor.path)
    return _load_test_cases(
        tests_root_path,
        test_type,
        handler_filter,
        config_descriptor.config_type,
        config,
    )
