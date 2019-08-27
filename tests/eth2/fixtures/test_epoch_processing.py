from eth2.beacon.tools.fixtures.config_types import Minimal
from eth2.beacon.tools.fixtures.test_gen import (
    generate_pytests_from_eth2_fixture,
    pytest_from_eth2_fixture,
)
from eth2.beacon.tools.fixtures.test_types.epoch_processing import (
    EpochProcessingTestType,
)


def pytest_generate_tests(metafunc):
    generate_pytests_from_eth2_fixture(metafunc)


@pytest_from_eth2_fixture(
    {
        "config_types": (Minimal,),
        "test_types": {
            EpochProcessingTestType: lambda handler: handler.name == "crosslinks"
        },
    }
)
def test_crosslinks(test_case):
    test_case.execute()


@pytest_from_eth2_fixture(
    {
        "config_types": (Minimal,),
        "test_types": {
            EpochProcessingTestType: lambda handler: handler.name
            == "justification_and_finalization"
        },
    }
)
def test_justification_and_finalization(test_case):
    test_case.execute()


@pytest_from_eth2_fixture(
    {
        "config_types": (Minimal,),
        "test_types": {
            EpochProcessingTestType: lambda handler: handler.name == "registry_updates"
        },
    }
)
def test_registry_updates(test_case):
    test_case.execute()


@pytest_from_eth2_fixture(
    {
        "config_types": (Minimal,),
        "test_types": {
            EpochProcessingTestType: lambda handler: handler.name == "slashings"
        },
    }
)
def test_slashings(test_case):
    test_case.execute()


@pytest_from_eth2_fixture(
    {
        "config_types": (Minimal,),
        "test_types": {
            EpochProcessingTestType: lambda handler: handler.name == "final_updates"
        },
    }
)
def test_final_updates(test_case):
    test_case.execute()
