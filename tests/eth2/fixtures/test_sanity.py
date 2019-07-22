import pytest


from eth2.beacon.tools.fixtures.config_types import (
    Minimal,
)
from eth2.beacon.tools.fixtures.config_descriptor import ConfigDescriptor
from eth2.beacon.tools.fixtures.parser import parse_tests
from eth2.beacon.tools.fixtures.test_types import (
    Sanity,
)


@pytest.mark.parametrize(
    (
        "config_type"
    ),
    (
        Minimal,
    )
)
@pytest.mark.parametrize(
    (
        "test_type"
    ),
    (
        Sanity,
    )
)
@pytest.mark.parametrize(
    (
        "handler_filter"
    ),
    (
        # run all handlers
        lambda _handler: True,
    )
)
def test_all_sanity_cases(tests_path,
                          config_path_provider,
                          config_type,
                          test_type,
                          handler_filter):
    test_cases = parse_tests(
        tests_path,
        test_type,
        handler_filter,
        config_descriptor=ConfigDescriptor(
            config_type,
            config_path_provider,
        ),
    )
    for t in test_cases:
        print(t)
    assert False
