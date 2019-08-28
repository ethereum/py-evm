from eth_utils import ValidationError
import pytest

from eth2.beacon.tools.fixtures.config_types import Minimal
from eth2.beacon.tools.fixtures.test_gen import (
    generate_pytests_from_eth2_fixture,
    pytest_from_eth2_fixture,
)
from eth2.beacon.tools.fixtures.test_types.sanity import SanityTestType


def pytest_generate_tests(metafunc):
    generate_pytests_from_eth2_fixture(metafunc)


@pytest_from_eth2_fixture(
    {
        "config_types": (Minimal,),
        "test_types": {SanityTestType: lambda handler: handler.name == "slots"},
    }
)
def test_slots(test_case):
    test_case.execute()


@pytest_from_eth2_fixture(
    {
        "config_types": (Minimal,),
        "test_types": {SanityTestType: lambda handler: handler.name == "blocks"},
    }
)
def test_blocks(test_case):
    if test_case.valid():
        test_case.execute()
    else:
        with pytest.raises(ValidationError):
            test_case.execute()
