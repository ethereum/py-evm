from dataclasses import dataclass

import pytest
from ssz.tools import from_formatted_dict

from eth2.beacon.genesis import is_valid_genesis_state
from eth2.beacon.tools.fixtures.config_name import ONLY_MINIMAL
from eth2.beacon.tools.fixtures.loading import get_bls_setting
from eth2.beacon.tools.fixtures.test_case import BaseTestCase
from eth2.beacon.tools.misc.ssz_vector import override_lengths
from eth2.beacon.types.states import BeaconState
from tests.eth2.fixtures.helpers import get_test_cases
from tests.eth2.fixtures.path import BASE_FIXTURE_PATH, ROOT_PROJECT_DIR

# Test files
RUNNER_FIXTURE_PATH = BASE_FIXTURE_PATH / "genesis"
HANDLER_FIXTURE_PATHES = (RUNNER_FIXTURE_PATH / "validity",)
FILTERED_CONFIG_NAMES = ONLY_MINIMAL


#
#  Test format
#
@dataclass
class GenesisValidityTestCase(BaseTestCase):
    bls_setting: bool
    description: str
    genesis: BeaconState
    is_valid: bool


def parse_genesis_validity_test_case(test_case, handler, index, config):
    override_lengths(config)

    bls_setting = get_bls_setting(test_case)
    genesis = from_formatted_dict(test_case["genesis"], BeaconState)
    is_valid = test_case["is_valid"]

    return GenesisValidityTestCase(
        handler=handler,
        index=index,
        bls_setting=bls_setting,
        description=test_case["description"],
        genesis=genesis,
        is_valid=is_valid,
    )


all_test_cases = get_test_cases(
    root_project_dir=ROOT_PROJECT_DIR,
    fixture_pathes=HANDLER_FIXTURE_PATHES,
    config_names=FILTERED_CONFIG_NAMES,
    parse_test_case_fn=parse_genesis_validity_test_case,
)


@pytest.mark.parametrize("test_case, config", all_test_cases)
def test_genesis_validity_fixture(config, test_case):
    assert test_case.is_valid == is_valid_genesis_state(test_case.genesis, config)
