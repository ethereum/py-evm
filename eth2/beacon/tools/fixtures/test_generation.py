import itertools
from typing import Any, Callable, Dict, Generator, Optional, Sequence, Set, Tuple, Type

from eth_utils.toolz import merge_with, thread_last
from typing_extensions import Protocol

from eth2.beacon.tools.fixtures.config_types import (
    ConfigType,
    General,
    Mainnet,
    Minimal,
)
from eth2.beacon.tools.fixtures.fork_types import ForkType, Phase0
from eth2.beacon.tools.fixtures.parser import parse_test_suites
from eth2.beacon.tools.fixtures.test_case import TestCase
from eth2.beacon.tools.fixtures.test_handler import Input, Output, TestHandler
from eth2.beacon.tools.fixtures.test_types import HandlerType, TestType

TestSuiteDescriptor = Tuple[
    Tuple[TestType[Any], TestHandler[Any, Any]], ConfigType, ForkType
]


class DecoratorTarget(Protocol):
    __eth2_fixture_config: Dict[str, Any]


class ConfigProtocol(Protocol):
    config: str


class OptionProtocol(Protocol):
    option: ConfigProtocol


# NOTE: ``pytest`` does not export the ``Metafunc`` class so we
# make a new type here to stand in for it.
class Metafunc(Protocol):
    function: DecoratorTarget

    config: OptionProtocol

    def parametrize(
        self, param_name: str, argvals: Tuple[TestCase, ...], ids: Tuple[str, ...]
    ) -> None:
        ...


def pytest_from_eth2_fixture(
    config: Dict[str, Any]
) -> Callable[[DecoratorTarget], DecoratorTarget]:
    """
    This function attaches the testing ``config`` to the ``func`` via the
    ``decorator``. The idea here is to just communicate this data to
    later stages of the test generation.
    """

    def decorator(func: DecoratorTarget) -> DecoratorTarget:
        func.__eth2_fixture_config = config
        return func

    return decorator


def _config_from_str(config_str: str) -> Type[ConfigType]:
    if config_str == Mainnet.name:
        return Mainnet
    elif config_str == Minimal.name:
        return Minimal
    elif config_str == General.name:
        return General
    else:
        raise AssertionError("invalid name request for eth2 config")


def _eth2_config_from(metafunc: Metafunc) -> Optional[Tuple[Type[ConfigType]]]:
    """
    Parse the configuration requested via command line parameter ``config``.

    NOTE: currently only takes one option but could be extended to respect a
    comma-separated list of several configuration options.
    """
    config_str = metafunc.config.option.config
    if config_str:
        return (_config_from_str(config_str),)
    return None


def _keep_first_some(values: Sequence[Any]) -> Any:
    """
    Used to find valid configuration option.
    Expect two objects in ``values``, return the first non-None value,
    going in reverse to respect precedence.
    """
    if len(values) == 1:
        return values[0]

    for value in reversed(values):
        if value:
            return value
    raise AssertionError(
        "``_keep_first_some`` should find at least one valid option; check configuration."
    )


def _read_request_from_metafunc(metafunc: Metafunc) -> Dict[str, Any]:
    """
    The ``metafunc.function`` has an ad-hoc property given in the top-level test harness
    decorator that communicates the caller's request to this library.

    This function also checks the ``metafunc`` for an eth2 config option and applies it.
    Supplying the configuration via the command line parameter overwrites any configuration
    given in the written request.
    """
    fn = metafunc.function
    request = fn.__eth2_fixture_config
    if "config_types" in request:
        return merge_with(
            _keep_first_some, request, {"config_types": _eth2_config_from(metafunc)}
        )
    else:
        return request


requested_config_types: Set[ConfigType] = set()


def _add_config_type_to_tracking_set(config: ConfigType) -> None:
    if len(requested_config_types) == 0:
        requested_config_types.add(config)


def _check_only_one_config_type(config_type: ConfigType) -> None:
    """
    Given the way we currently handle setting the size of dynamic SSZ types,
    we can only run one type of configuration *per process*.
    """
    if config_type not in requested_config_types:
        raise Exception(
            "Can only run a _single_ type of configuration per process; "
            "please inspect pytest configuration."
        )


def _generate_test_suite_descriptors_from(
    eth2_fixture_request: Dict[str, Any]
) -> Tuple[Any, ...]:
    # NOTE: fork types are not currently configurable
    fork_types = (Phase0,)

    if "config_types" in eth2_fixture_request:
        config_types = eth2_fixture_request["config_types"]
        # NOTE: in an ideal world, a user of the test generator can
        # specify multiple types of config in one test run. They could also specify
        # multiple test runs w/ disparate configurations. Given the way we currently
        # handle setting SSZ bounds (globally!), we have to enforce the invariant of only
        # one type of config per process.
        if len(config_types) != 1:
            raise Exception(
                "only run one config type per process, due to overwriting SSZ bounds"
            )
        config_type = config_types[0]
        _add_config_type_to_tracking_set(config_type)
        _check_only_one_config_type(config_type)
        configs_to_exclude = eth2_fixture_request.get("exclude_for", ())
        should_include_handler = config_type not in configs_to_exclude
    else:
        config_types = (General,)
        should_include_handler = True

    test_types = eth2_fixture_request["test_types"]

    # if a subset of handlers is not provided,
    # run all handlers for a given test type.
    if not isinstance(test_types, Dict):
        test_types = {test_type: lambda _handler: True for test_type in test_types}

    selected_handlers: Tuple[Tuple[TestType[Any], TestHandler[Any, Any]], ...] = tuple()
    for test_type, handler_filter in test_types.items():
        for handler in test_type.handlers:
            if handler_filter(handler) and should_include_handler:
                selected_handlers += ((test_type, handler),)

    return tuple(itertools.product(selected_handlers, config_types, fork_types))


def _generate_pytest_case_from(
    test_type: TestType[HandlerType],
    handler_type: TestHandler[Input, Output],
    suite_name: str,
    config_type: ConfigType,
    fork_type: ForkType,
    test_case: TestCase,
) -> Tuple[TestCase, str]:
    """
    id format:
      f"{TEST_TYPE_NAME}_{CONFIG_TYPE_NAME}_{FORK_TYPE_NAME}_{HANDLER_TYPE_NAME}_{TEST_SUITE_NAME}_{TEST_CASE_NAME}"  # noqa: E501
    """
    test_name = test_type.name
    handler_name = handler_type.name
    config_name = config_type.name
    fork_name = fork_type.name

    test_id = thread_last(
        (test_name, config_name, fork_name, handler_name, suite_name, test_case.name),
        (filter, lambda component: component != ""),
        lambda components: "_".join(components),
    )
    return test_case, test_id


def _generate_pytest_cases_from_test_suite_descriptors(
    test_suite_descriptors: Tuple[TestSuiteDescriptor, ...]
) -> Generator[Tuple[TestCase, str], None, None]:
    for ((test_type, handler_type), config_type, fork_type) in test_suite_descriptors:
        test_suites = parse_test_suites(test_type, handler_type, config_type, fork_type)
        for suite in test_suites:
            for test_case in suite.test_cases:
                yield _generate_pytest_case_from(
                    test_type,
                    handler_type,
                    suite.name,
                    config_type,
                    fork_type,
                    test_case,
                )


def generate_pytests_from_eth2_fixture(metafunc: Metafunc) -> None:
    """
    Generate all the test cases requested by the config (attached to ``metafunc``'s
    function object) and inject them via ``metafunc.parametrize``.
    """
    eth2_fixture_request = _read_request_from_metafunc(metafunc)
    test_suite_descriptors = _generate_test_suite_descriptors_from(eth2_fixture_request)
    pytest_cases = tuple(
        _generate_pytest_cases_from_test_suite_descriptors(test_suite_descriptors)
    )
    if pytest_cases:
        argvals, ids = zip(*pytest_cases)
    else:
        argvals, ids = (), ()

    metafunc.parametrize("test_case", argvals, ids=ids)
