from eth2.beacon.tools.fixtures.test_gen import (
    generate_pytests_from_eth2_fixture,
    pytest_from_eth2_fixture,
)
from eth2.beacon.tools.fixtures.test_types.bls import BLSTestType


def pytest_generate_tests(metafunc):
    generate_pytests_from_eth2_fixture(metafunc)


@pytest_from_eth2_fixture(
    {"test_types": {BLSTestType: lambda handler: handler.name == "aggregate_pubkeys"}}
)
def test_aggregate_pubkeys(test_case):
    test_case.execute()


@pytest_from_eth2_fixture(
    {"test_types": {BLSTestType: lambda handler: handler.name == "aggregate_sigs"}}
)
def test_aggregate_sigs(test_case):
    test_case.execute()


@pytest_from_eth2_fixture(
    {"test_types": {BLSTestType: lambda handler: handler.name == "priv_to_pub"}}
)
def test_priv_to_pub(test_case):
    test_case.execute()


@pytest_from_eth2_fixture(
    {"test_types": {BLSTestType: lambda handler: handler.name == "sign_msg"}}
)
def test_sign_msg(test_case):
    test_case.execute()
