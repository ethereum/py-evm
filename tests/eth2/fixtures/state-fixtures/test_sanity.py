import os
from pathlib import Path
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
    from_formatted_dict,
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
from eth2.beacon.tools.fixtures.test_case import (
    BaseStateTestCase,
)
from tests.eth2.fixtures.helpers import (
    get_test_cases,
)


# Test files
# ROOT_PROJECT_DIR = Path(__file__).cwd()
ROOT_PROJECT_DIR = Path(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
)

BASE_FIXTURE_PATH = ROOT_PROJECT_DIR / 'eth2-fixtures' / 'tests'

SANITY_FIXTURE_PATH = BASE_FIXTURE_PATH / 'sanity'
FIXTURE_PATHES = (
    SANITY_FIXTURE_PATH / 'blocks',
    SANITY_FIXTURE_PATH / 'slots',
)


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
    # default is free to choose, so we choose OFF
    if 'bls_setting' not in test_case or test_case['bls_setting'] == 2:
        bls_setting = False
    else:
        bls_setting = True

    override_lengths(config)
    pre = from_formatted_dict(test_case['pre'], BeaconState)
    if test_case['post'] is not None:
        post = from_formatted_dict(test_case['post'], BeaconState)
        is_valid = True
    else:
        is_valid = False

    if 'blocks' in test_case:
        blocks = tuple(from_formatted_dict(block, BeaconBlock) for block in test_case['blocks'])
    else:
        blocks = ()

    slots = test_case['slots'] if 'slots' in test_case else 0

    return SanityTestCase(
        line_number=test_case.lc.line,
        bls_setting=bls_setting,
        description=test_case['description'],
        pre=pre,
        post=post if is_valid else None,
        is_valid=is_valid,
        slots=slots,
        blocks=blocks,
    )


all_test_cases = get_test_cases(
    root_project_dir=ROOT_PROJECT_DIR,
    fixture_pathes=FIXTURE_PATHES,
    parse_test_case_fn=parse_sanity_test_case
)


@pytest.mark.parametrize(
    "test_case, config",
    all_test_cases
)
def test_state(base_db, config, test_case):
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
    post_state = advance_to_slot(sm, post_state, test_case.slots)

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
