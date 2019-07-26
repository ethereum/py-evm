from dataclasses import (
    dataclass,
)
import pytest

from eth_utils import (
    ValidationError,
)

from eth2.beacon.tools.misc.ssz_vector import (
    override_lengths,
)
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.blocks import BeaconBlock, BeaconBlockBody
from eth2.beacon.types.states import BeaconState
from eth2.beacon.tools.fixtures.config_name import (
    ONLY_MINIMAL,
)
from eth2.beacon.tools.fixtures.helpers import (
    run_state_execution,
    validate_state,
)
from eth2.beacon.state_machines.forks.serenity.operation_processing import (
    process_attestations,
)
from eth2.beacon.tools.fixtures.loading import (
    get_bls_setting,
    get_operation_or_header,
    get_states,
)
from eth2.beacon.tools.fixtures.test_case import (
    OperationCase,
)

from tests.eth2.fixtures.helpers import (
    get_test_cases,
    get_chaindb_of_config,
    get_sm_class_of_config,
)
from tests.eth2.fixtures.path import (
    BASE_FIXTURE_PATH,
    ROOT_PROJECT_DIR,
)


# Test files
RUNNER_FIXTURE_PATH = BASE_FIXTURE_PATH / 'operations'
HANDLER_FIXTURE_PATHES = (
    RUNNER_FIXTURE_PATH / 'attestation',
)
FILTERED_CONFIG_NAMES = ONLY_MINIMAL


#
# Helpers for generating test suite
#
def parse_operation_test_case(test_case, index, config):
    override_lengths(config)

    bls_setting = get_bls_setting(test_case)
    pre, post, is_valid = get_states(test_case, BeaconState)
    operation = get_operation_or_header(test_case, Attestation, 'attestation')

    return OperationCase(
        index=index,
        bls_setting=bls_setting,
        description=test_case['description'],
        pre=pre,
        operation=operation,
        post=post,
        is_valid=is_valid,
    )


all_test_cases = get_test_cases(
    root_project_dir=ROOT_PROJECT_DIR,
    fixture_pathes=HANDLER_FIXTURE_PATHES,
    config_names=FILTERED_CONFIG_NAMES,
    parse_test_case_fn=parse_operation_test_case,
)


@pytest.mark.parametrize(
    "test_case, config",
    all_test_cases
)
def test_sanity_fixture(config, test_case):
    post_state = test_case.pre
    block = BeaconBlock().copy(
        body=BeaconBlockBody(
            attestations=(test_case.operation,),
        )
    )
    if test_case.is_valid:
        post_state = process_attestations(post_state, block, config)
        validate_state(test_case.post, post_state)
    else:
        with pytest.raises((ValidationError, IndexError)):
            process_attestations(post_state, block, config)
