import pytest

from eth_utils import ValidationError

from eth2.beacon.exceptions import SignatureError
from eth2.beacon.tools.misc.ssz_vector import override_lengths
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.attester_slashings import AttesterSlashing
from eth2.beacon.types.blocks import BeaconBlock, BeaconBlockBody
from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.proposer_slashings import ProposerSlashing
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.transfers import Transfer
from eth2.beacon.types.voluntary_exits import VoluntaryExit


from eth2.beacon.tools.fixtures.config_name import ONLY_MINIMAL
from eth2.beacon.tools.fixtures.helpers import validate_state
from eth2.beacon.state_machines.forks.serenity.operation_processing import (
    process_attestations,
    process_attester_slashings,
    process_deposits,
    process_proposer_slashings,
    process_transfers,
    process_voluntary_exits,
)
from eth2.beacon.tools.fixtures.loading import (
    get_bls_setting,
    get_operation_or_header,
    get_states,
)
from eth2.beacon.tools.fixtures.test_case import OperationCase

from tests.eth2.fixtures.helpers import get_test_cases
from tests.eth2.fixtures.path import BASE_FIXTURE_PATH, ROOT_PROJECT_DIR


# Test files
RUNNER_FIXTURE_PATH = BASE_FIXTURE_PATH / "operations"
HANDLER_FIXTURE_PATHES = (
    RUNNER_FIXTURE_PATH / "proposer_slashing",
    RUNNER_FIXTURE_PATH / "attester_slashing",
    RUNNER_FIXTURE_PATH / "attestation",
    RUNNER_FIXTURE_PATH / "deposit",
    RUNNER_FIXTURE_PATH / "voluntary_exit",
    RUNNER_FIXTURE_PATH / "transfer",
)
FILTERED_CONFIG_NAMES = ONLY_MINIMAL

handler_to_processing_call_map = {
    "proposer_slashing": (ProposerSlashing, process_proposer_slashings),
    "attester_slashing": (AttesterSlashing, process_attester_slashings),
    "attestation": (Attestation, process_attestations),
    "deposit": (Deposit, process_deposits),
    "voluntary_exit": (VoluntaryExit, process_voluntary_exits),
    "transfer": (Transfer, process_transfers),
}


#
# Helpers for generating test suite
#
def parse_operation_test_case(test_case, handler, index, config):
    config = config._replace(MAX_TRANSFERS=1)
    override_lengths(config)

    bls_setting = get_bls_setting(test_case)
    pre, post, is_valid = get_states(test_case, BeaconState)
    operation_class, _ = handler_to_processing_call_map[handler]
    operation = get_operation_or_header(test_case, operation_class, handler)

    return OperationCase(
        handler=handler,
        index=index,
        bls_setting=bls_setting,
        description=test_case["description"],
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


@pytest.mark.parametrize("test_case, config", all_test_cases)
def test_operation_fixture(config, test_case):
    config = config._replace(MAX_TRANSFERS=1)
    post_state = test_case.pre
    block = BeaconBlock().copy(
        body=BeaconBlockBody(
            **{test_case.handler + "s": (test_case.operation,)}  # TODO: it looks awful
        )
    )
    _, operation_processing = handler_to_processing_call_map[test_case.handler]

    if test_case.is_valid:
        post_state = operation_processing(post_state, block, config)
        validate_state(test_case.post, post_state)
    else:
        with pytest.raises((ValidationError, IndexError, SignatureError)):
            operation_processing(post_state, block, config)
