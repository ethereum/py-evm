from typing import (
    Tuple,
)

from dataclasses import (
    dataclass,
    field,
)
import pytest

from eth_utils import (
    ValidationError,
)
from ssz.tools import (
    to_formatted_dict,
)

from eth2.configs import (
    Eth2GenesisConfig,
)
from eth2.beacon.db.chain import BeaconChainDB
from eth2.beacon.operations.attestation_pool import AttestationPool
from eth2.beacon.state_machines.forks.serenity import (
    SerenityStateMachine,
)
from eth2.beacon.tools.builder.proposer import (
    advance_to_slot,
)
from eth2.beacon.tools.misc.ssz_vector import (
    override_lengths,
)
from eth2.beacon.types.blocks import BeaconBlock
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import (
    Slot,
)
from eth2.beacon.tools.fixtures.config_name import (
    ONLY_MINIMAL,
)
from eth2.beacon.tools.fixtures.test_case import (
    BaseStateTestCase,
)
from eth2.beacon.tools.fixtures.loading import (
    get_bls_setting,
    get_blocks,
    get_slots,
    get_states,
)
from tests.eth2.fixtures.helpers import (
    get_test_cases,
)
from tests.eth2.fixtures.path import (
    BASE_FIXTURE_PATH,
    ROOT_PROJECT_DIR,
)


# Test files
SANITY_FIXTURE_PATH = BASE_FIXTURE_PATH / 'sanity'
FIXTURE_PATHES = (
    SANITY_FIXTURE_PATH,
)
FILTERED_CONFIG_NAMES = ONLY_MINIMAL


#
# Sanity test_format
#
@dataclass
class SanityTestCase(BaseStateTestCase):
    slots: Slot = 0
    blocks: Tuple[BeaconBlock, ...] = field(default_factory=tuple)


#
# Helpers for generating test suite
#
def parse_sanity_test_case(test_case, config):
    override_lengths(config)

    bls_setting = get_bls_setting(test_case)
    pre, post, is_valid = get_states(test_case, BeaconState)
    blocks = get_blocks(test_case, BeaconBlock)
    slots = get_slots(test_case)

    return SanityTestCase(
        line_number=test_case.lc.line,
        bls_setting=bls_setting,
        description=test_case['description'],
        pre=pre,
        post=post,
        is_valid=is_valid,
        slots=slots,
        blocks=blocks,
    )


all_test_cases = get_test_cases(
    root_project_dir=ROOT_PROJECT_DIR,
    fixture_pathes=FIXTURE_PATHES,
    config_names=FILTERED_CONFIG_NAMES,
    parse_test_case_fn=parse_sanity_test_case,
)


@pytest.mark.parametrize(
    "test_case, config",
    all_test_cases
)
def test_sanity_fixture(base_db, config, test_case):
    execute_state_transtion(test_case, config, base_db)


def execute_state_transtion(test_case, config, base_db):
    sm_class = SerenityStateMachine.configure(
        __name__='SerenityStateMachineForTesting',
        config=config,
    )
    chaindb = BeaconChainDB(base_db, Eth2GenesisConfig(config))
    attestation_pool = AttestationPool()

    post_state = test_case.pre.copy()

    sm = sm_class(chaindb, attestation_pool, None, post_state)
    slot = test_case.pre.slot + test_case.slots
    post_state = advance_to_slot(sm, post_state, slot)

    if test_case.is_valid:
        for block in test_case.blocks:
            sm = sm_class(chaindb, attestation_pool, None, post_state)
            post_state, _ = sm.import_block(block)

        # Use dict diff, easier to see the diff
        dict_post_state = to_formatted_dict(post_state, BeaconState)
        dict_expected_state = to_formatted_dict(test_case.post, BeaconState)
        for key, value in dict_expected_state.items():
            if isinstance(value, list):
                value = tuple(value)
            assert dict_post_state[key] == value
    else:
        with pytest.raises(ValidationError):
            for block in test_case.blocks:
                sm = sm_class(chaindb, attestation_pool, None, post_state)
                post_state, _ = sm.import_block(block)
