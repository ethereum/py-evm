from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional, Tuple, Union

from eth_typing import BLSPubkey, BLSSignature
from eth_utils import decode_hex, to_tuple

from eth2.beacon.tools.fixtures.config_types import ConfigType
from eth2.beacon.tools.fixtures.fork_types import ForkType
from eth2.beacon.tools.fixtures.format_type import FormatType
from eth2.beacon.tools.fixtures.loading import load_config_at_path, load_yaml_at
from eth2.beacon.tools.fixtures.test_case import TestCase
from eth2.beacon.tools.fixtures.test_handler import Input, Output, TestHandler
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
    parts: Tuple[Path]
    format_type: FormatType


@dataclass
class TestSuiteDescriptor:
    name: str
    test_case_descriptors: Tuple[TestCaseDescriptor]


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


def _load_parts(
    parts: Iterable[Path], format_type: FormatType
) -> Dict[str, Dict[str, Any]]:
    return {
        part.name.replace(f".{format_type.name}", ""): load_yaml_at(part)
        for part in parts
    }


@to_tuple
def _parse_test_cases(
    config: Optional[Eth2Config],
    test_handler: TestHandler[Input, Output],
    test_case_descriptors: Iterable[TestCaseDescriptor],
) -> Iterator[TestCase]:
    for descriptor in test_case_descriptors:
        test_case_parts = _load_parts(descriptor.parts, descriptor.format_type)
        yield TestCase(descriptor.name, test_handler, test_case_parts, config)


def _load_test_case(
    test_case_path: Path, format_type: FormatType
) -> TestCaseDescriptor:
    parts = (
        part_path
        for part_path in test_case_path.iterdir()
        if part_path.suffix[1:] == format_type.name
    )
    return TestCaseDescriptor(test_case_path.name, parts, format_type)


@to_tuple
def _discover_test_suite_from(
    test_handler_path: Path, format_type: FormatType
) -> Iterator[TestSuiteDescriptor]:
    for test_suite in test_handler_path.iterdir():
        test_case_descriptors = (
            _load_test_case(test_case_path, format_type)
            for test_case_path in test_suite.iterdir()
        )
        yield TestSuiteDescriptor(test_suite.name, test_case_descriptors)


@to_tuple
def _load_and_parse_test_suites(
    tests_path: Path,
    test_type: TestType[HandlerType],
    test_handler: TestHandler[Input, Output],
    config_type: ConfigType,
    fork_type: ForkType,
    format_type: FormatType,
) -> Iterator[TestSuite]:
    test_handler_path = _build_test_handler_path(
        tests_path, test_type, test_handler, config_type, fork_type
    )

    test_suite_descriptors = _discover_test_suite_from(test_handler_path, format_type)

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
    format_type: FormatType,
) -> Tuple[TestSuite]:
    """
    Find all of the test suites (including their respective test cases) given a fixed
    ``test_type``, ``test_handler``, ``config_type``, ``fork_type`` and ``format_type``.

    This search directly corresponds to finding subtrees of the file hierarchy
    under particular paths fixed by the function arguments.
    """
    project_root_dir = _find_project_root_dir(TESTS_ROOT_PATH)
    tests_path = project_root_dir / TESTS_ROOT_PATH / TESTS_PATH
    return _load_and_parse_test_suites(
        tests_path, test_type, test_handler, config_type, fork_type, format_type
    )


def get_input_bls_pubkeys(
    test_case: Dict[str, Any]
) -> Dict[str, Tuple[BLSPubkey, ...]]:
    return {
        "pubkeys": tuple(BLSPubkey(decode_hex(item)) for item in test_case["input"])
    }


def get_input_bls_signatures(
    test_case: Dict[str, Any]
) -> Dict[str, Tuple[BLSSignature, ...]]:
    return {
        "signatures": tuple(
            BLSSignature(decode_hex(item)) for item in test_case["input"]
        )
    }


def get_input_bls_privkey(test_case: Dict[str, Any]) -> Dict[str, int]:
    return {"privkey": int.from_bytes(decode_hex(test_case["input"]), "big")}


def get_input_sign_message(test_case: Dict[str, Any]) -> Dict[str, Union[int, bytes]]:
    return {
        "privkey": int.from_bytes(decode_hex(test_case["input"]["privkey"]), "big"),
        "message_hash": decode_hex(test_case["input"]["message"]),
        "domain": decode_hex(test_case["input"]["domain"]),
    }


def get_output_bls_pubkey(test_case: Dict[str, Any]) -> BLSPubkey:
    return BLSPubkey(decode_hex(test_case["output"]))


def get_output_bls_signature(test_case: Dict[str, Any]) -> BLSSignature:
    return BLSSignature(decode_hex(test_case["output"]))
