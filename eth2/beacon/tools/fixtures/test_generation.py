import itertools
from typing import Any, Callable, Dict, Generator, Iterator, Set, Tuple

from eth_utils.toolz import thread_last
from typing_extensions import Protocol

from eth2.beacon.tools.fixtures.config_types import ConfigType, General
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


# NOTE: ``pytest`` does not export the ``Metafunc`` class so we
# make a new type here to stand in for it.
class Metafunc(Protocol):
    function: DecoratorTarget

    def parametrize(
        self, param_name: str, argvals: Tuple[TestCase, ...], ids: Tuple[str, ...]
    ) -> None:
        ...


def pytest_from_eth2_fixture(
    config: Dict[str, Any]
) -> Callable[[DecoratorTarget], DecoratorTarget]:
    """
    This function attaches the ``config`` to the ``func`` via the
    ``decorator``. The idea here is to just communicate this data to
    later stages of the test generation.
    """

    def decorator(func: DecoratorTarget) -> DecoratorTarget:
        func.__eth2_fixture_config = config
        return func

    return decorator


def _read_request_from_metafunc(metafunc: Metafunc) -> Dict[str, Any]:
    fn = metafunc.function
    return fn.__eth2_fixture_config


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
) -> Tuple[TestSuiteDescriptor, ...]:
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
    else:
        config_types = (General,)

    test_types = eth2_fixture_request["test_types"]

    # special case only one handler, "core"
    if not isinstance(test_types, Dict):
        test_types = {
            _type: lambda handler: handler.name == "core" for _type in test_types
        }

    selected_handlers: Tuple[Tuple[TestType[Any], TestHandler[Any, Any]], ...] = tuple()
    for test_type, handler_filter in test_types.items():
        for handler in test_type.handlers:
            if handler_filter(handler) or handler.name == "core":
                selected_handler = (test_type, handler)
                selected_handlers += selected_handler
    result: Iterator[Any] = itertools.product(
        (selected_handlers,), config_types, fork_types
    )
    return tuple(result)


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
      f"{TEST_TYPE_NAME}_{HANDLER_TYPE_NAME}_{TEST_SUITE_NAME}_{TEST_CASE_NAME}:{CONFIG_TYPE_NAME}_{FORK_TYPE_NAME}"  # noqa: E501
    """
    # special case only one handler "core"
    test_name = test_type.name
    if len(test_type.handlers) == 1 or handler_type.name == "core":
        handler_name = ""
    else:
        handler_name = handler_type.name

    test_id_prefix = thread_last(
        (test_name, handler_name, suite_name, test_case.name),
        (filter, lambda component: component != ""),
        lambda components: "_".join(components),
    )
    test_id = f"{test_id_prefix}:{config_type.name}_{fork_type.name}"
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
