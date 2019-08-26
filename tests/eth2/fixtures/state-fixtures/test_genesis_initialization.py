from dataclasses import dataclass, field
from typing import Tuple

from eth_typing import Hash32
from eth_utils import decode_hex
import pytest
from ssz.tools import from_formatted_dict

from eth2.beacon.genesis import initialize_beacon_state_from_eth1
from eth2.beacon.tools.fixtures.config_name import ONLY_MINIMAL
from eth2.beacon.tools.fixtures.helpers import validate_state
from eth2.beacon.tools.fixtures.loading import get_bls_setting, get_deposits
from eth2.beacon.tools.fixtures.test_case import BaseTestCase
from eth2.beacon.tools.misc.ssz_vector import override_lengths
from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import Timestamp
from tests.eth2.fixtures.helpers import get_test_cases
from tests.eth2.fixtures.path import BASE_FIXTURE_PATH, ROOT_PROJECT_DIR

# Test files
RUNNER_FIXTURE_PATH = BASE_FIXTURE_PATH / "genesis"
HANDLER_FIXTURE_PATHES = (RUNNER_FIXTURE_PATH / "initialization",)
FILTERED_CONFIG_NAMES = ONLY_MINIMAL


#
#  Test format
#
@dataclass
class GenesisInitializationTestCase(BaseTestCase):
    bls_setting: bool
    description: str
    eth1_block_hash: Hash32
    eth1_timestamp: Timestamp
    state: BeaconState
    deposits: Tuple[Deposit, ...] = field(default_factory=tuple)


#
# Helpers for generating test suite
#
def parse_genesis_initialization_test_case(test_case, handler, index, config):
    override_lengths(config)

    bls_setting = get_bls_setting(test_case)
    eth1_block_hash = decode_hex(test_case["eth1_block_hash"])
    eth1_timestamp = test_case["eth1_timestamp"]
    state = from_formatted_dict(test_case["state"], BeaconState)
    deposits = get_deposits(test_case, Deposit)

    return GenesisInitializationTestCase(
        handler=handler,
        index=index,
        bls_setting=bls_setting,
        description=test_case["description"],
        eth1_block_hash=eth1_block_hash,
        eth1_timestamp=eth1_timestamp,
        state=state,
        deposits=deposits,
    )


all_test_cases = get_test_cases(
    root_project_dir=ROOT_PROJECT_DIR,
    fixture_pathes=HANDLER_FIXTURE_PATHES,
    config_names=FILTERED_CONFIG_NAMES,
    parse_test_case_fn=parse_genesis_initialization_test_case,
)


@pytest.mark.parametrize("test_case, config", all_test_cases)
def test_genesis_initialization_fixture(config, test_case):
    result_state = initialize_beacon_state_from_eth1(
        eth1_block_hash=test_case.eth1_block_hash,
        eth1_timestamp=test_case.eth1_timestamp,
        deposits=test_case.deposits,
        config=config,
    )

    validate_state(test_case.state, result_state)
