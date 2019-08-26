from dataclasses import dataclass

from eth_utils import ValidationError
import pytest

from eth2.beacon.tools.fixtures.config_name import ONLY_MINIMAL
from eth2.beacon.tools.fixtures.helpers import run_state_execution, validate_state
from eth2.beacon.tools.fixtures.loading import (
    get_blocks,
    get_bls_setting,
    get_slots,
    get_states,
)
from eth2.beacon.tools.fixtures.test_case import StateTestCase
from eth2.beacon.tools.misc.ssz_vector import override_lengths
from eth2.beacon.types.blocks import BeaconBlock
from eth2.beacon.types.states import BeaconState
from tests.eth2.fixtures.helpers import (
    get_chaindb_of_config,
    get_sm_class_of_config,
    get_test_cases,
)
from tests.eth2.fixtures.path import BASE_FIXTURE_PATH, ROOT_PROJECT_DIR

# Test files
RUNNER_FIXTURE_PATH = BASE_FIXTURE_PATH / "sanity"
HANDLER_FIXTURE_PATHES = (RUNNER_FIXTURE_PATH,)
FILTERED_CONFIG_NAMES = ONLY_MINIMAL


#
#  Test format
#
@dataclass
class SanityTestCase(StateTestCase):
    pass


#
# Helpers for generating test suite
#
def parse_sanity_test_case(test_case, handler, index, config):
    override_lengths(config)

    bls_setting = get_bls_setting(test_case)
    pre, post, is_valid = get_states(test_case, BeaconState)
    blocks = get_blocks(test_case, BeaconBlock)
    slots = get_slots(test_case)

    return SanityTestCase(
        handler=handler,
        index=index,
        bls_setting=bls_setting,
        description=test_case["description"],
        pre=pre,
        post=post,
        is_valid=is_valid,
        slots=slots,
        blocks=blocks,
    )


all_test_cases = get_test_cases(
    root_project_dir=ROOT_PROJECT_DIR,
    fixture_pathes=HANDLER_FIXTURE_PATHES,
    config_names=FILTERED_CONFIG_NAMES,
    parse_test_case_fn=parse_sanity_test_case,
)


@pytest.mark.parametrize("test_case, config", all_test_cases)
def test_sanity_fixture(base_db, config, test_case, empty_attestation_pool):
    sm_class = get_sm_class_of_config(config)
    chaindb = get_chaindb_of_config(base_db, config)

    post_state = test_case.pre
    if test_case.is_valid:
        post_state = run_state_execution(
            test_case, sm_class, chaindb, empty_attestation_pool, post_state
        )

        validate_state(test_case.post, post_state)
    else:
        with pytest.raises(ValidationError):
            run_state_execution(
                test_case, sm_class, chaindb, empty_attestation_pool, post_state
            )
