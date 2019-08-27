import itertools
from typing import Any, Dict

from eth2.beacon.tools.fixtures.parser import parse_test_suite


def pytest_from_eth2_fixture(config: Dict[str, Any]):
    """
    This function attaches the ``config`` to the ``func`` via the
    ``decorator``. The idea here is to just communicate this data to
    later stages of the test generation.
    """

    def decorator(func):
        func.__eth2_fixture_config = config
        return func

    return decorator


def _read_request_from_metafunc(metafunc):
    fn = metafunc.function
    return fn.__eth2_fixture_config


def _generate_test_suite_descriptors_from(eth2_fixture_request):
    config_types = eth2_fixture_request["config_types"]
    if len(config_types) != 1:
        raise Exception(
            "only run one config type per process, due to overwriting SSZ bounds"
        )
    test_types = eth2_fixture_request["test_types"]

    # special case only one handler, "core"
    if not isinstance(test_types, Dict):
        test_types = {
            _type: lambda handler: handler.name == "core" for _type in test_types
        }

    selected_handlers = tuple()
    for test_type, handler_filter in test_types.items():
        for handler in test_type.handlers:
            if handler_filter(handler) or handler.name == "core":
                selected_handler = (test_type, handler)
                selected_handlers += selected_handler
    return itertools.product((selected_handlers,), config_types)


def _generate_pytest_case_from(test_type, handler_type, config_type, test_case):
    # special case only one handler "core"
    if len(test_type.handlers) == 1 or handler_type.name == "core":
        test_id = f"{test_type.name}_{config_type.name}.yaml:" f"{test_case.index}"
    else:
        test_id = (
            f"{test_type.name}_{handler_type.name}_{config_type.name}.yaml:"
            f"{test_case.index}"
        )
    if test_case.description:
        test_id += f":{test_case.description}"
    return test_case, test_id


def _generate_pytest_cases_from_test_suite_descriptors(test_suite_descriptors):
    for (test_type, handler_type), config_type in test_suite_descriptors:
        test_suite = parse_test_suite(test_type, handler_type, config_type)
        for test_case in test_suite.test_cases:
            yield _generate_pytest_case_from(
                test_type, handler_type, config_type, test_case
            )


def generate_pytests_from_eth2_fixture(metafunc) -> None:
    """
    Generate all the test cases requested by the config (attached to ``metafunc``'s
    function object) and inject them via ``metafunc.parametrize``.
    """
    eth2_fixture_request = _read_request_from_metafunc(metafunc)
    test_suite_descriptors = _generate_test_suite_descriptors_from(eth2_fixture_request)
    pytest_cases = _generate_pytest_cases_from_test_suite_descriptors(
        test_suite_descriptors
    )
    if pytest_cases:
        argvals, ids = zip(*pytest_cases)
    else:
        argvals, ids = (), ()

    metafunc.parametrize("test_case", argvals, ids=ids)
