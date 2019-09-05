from eth2.beacon.tools.fixtures.config_types import Mainnet, Minimal
from eth2.beacon.tools.fixtures.test_generation import (
    generate_pytests_from_eth2_fixture,
    pytest_from_eth2_fixture,
)
from eth2.beacon.tools.fixtures.test_types.genesis import GenesisTestType


def pytest_generate_tests(metafunc):
    generate_pytests_from_eth2_fixture(metafunc)


@pytest_from_eth2_fixture(
    {
        "config_types": (Minimal,),
        "test_types": {GenesisTestType: lambda handler: handler.name == "validity"},
        "exclude_for": (Mainnet,),
    }
)
def test_validity(test_case):
    test_case.execute()


@pytest_from_eth2_fixture(
    {
        "config_types": (Minimal,),
        "test_types": {
            GenesisTestType: lambda handler: handler.name == "initialization"
        },
        "exclude_for": (Mainnet,),
    }
)
def test_initialization(test_case):
    test_case.execute()
