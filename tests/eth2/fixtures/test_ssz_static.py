from eth2.beacon.tools.fixtures.config_types import Minimal
from eth2.beacon.tools.fixtures.test_generation import (
    generate_pytests_from_eth2_fixture,
    pytest_from_eth2_fixture,
)
from eth2.beacon.tools.fixtures.test_types.ssz_static import SSZStaticTestType


def pytest_generate_tests(metafunc):
    generate_pytests_from_eth2_fixture(metafunc)


@pytest_from_eth2_fixture(
    {"config_types": (Minimal,), "test_types": (SSZStaticTestType,)}
)
def test_all(test_case):
    test_case.execute()
