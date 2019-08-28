from eth2.beacon.tools.fixtures.config_types import Minimal
from eth2.beacon.tools.fixtures.test_gen import (
    generate_pytests_from_eth2_fixture,
    pytest_from_eth2_fixture,
)
from eth2.beacon.tools.fixtures.test_types.shuffling import ShufflingTestType


def pytest_generate_tests(metafunc):
    generate_pytests_from_eth2_fixture(metafunc)


@pytest_from_eth2_fixture(
    {"config_types": (Minimal,), "test_types": (ShufflingTestType,)}
)
def test_minimal(test_case):
    test_case.execute()


# @pytest_from_eth2_fixture({"config_types": (Full,), "test_types": (ShufflingTestType,)})
# def test_full(test_case):
#     test_case.execute()
