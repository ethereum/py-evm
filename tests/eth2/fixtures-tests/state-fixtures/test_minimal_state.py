from pathlib import Path
import pytest
from ruamel.yaml import (
    YAML,
)

from eth_utils import (
    to_tuple,
)
from py_ecc import bls  # noqa: F401
from ssz.tools import (
    from_formatted_dict,
    to_formatted_dict,
)


from eth2.configs import (
    Eth2Config,
    Eth2GenesisConfig,
)
from eth2.beacon.db.chain import BeaconChainDB
from eth2.beacon.tools.misc.ssz_vector import (
    override_vector_lengths,
)
from eth2.beacon.types.states import BeaconState
from eth2.beacon.state_machines.forks.serenity.blocks import SerenityBeaconBlock
from eth2.beacon.state_machines.forks.serenity import (
    SerenityStateMachine,
)

# Test files
ROOT_PROJECT_DIR = Path(__file__).cwd()

BASE_FIXTURE_PATH = ROOT_PROJECT_DIR / 'eth2-fixtures' / 'state'

FIXTURE_FILE_NAMES = [
    "sanity-check_small-config_32-vals.yaml",
    "sanity-check_default-config_100-vals.yaml",
]


#
# Mock bls verification for these tests
#
def mock_bls_verify(message_hash, pubkey, signature, domain):
    return True


def mock_bls_verify_multiple(pubkeys,
                             message_hashes,
                             signature,
                             domain):
    return True


@pytest.fixture(autouse=True)
def mock_bls(mocker, request):
    if 'noautofixture' in request.keywords:
        return

    mocker.patch('py_ecc.bls.verify', side_effect=mock_bls_verify)
    mocker.patch('py_ecc.bls.verify_multiple', side_effect=mock_bls_verify_multiple)


#
# Helpers for generating test suite
#
def get_all_test_cases(file_names):
    test_cases = {}
    yaml = YAML()
    for file_name in file_names:
        file_to_open = BASE_FIXTURE_PATH / file_name
        with open(file_to_open, 'U') as f:
            # TODO: `proof_of_possession` is used in v0.5.1 spec and will be renamed to `signature`
            # Trinity renamed it ahead due to py-ssz signing_root requirements
            new_text = f.read().replace('proof_of_possession', 'signature')
            try:
                data = yaml.load(new_text)
                test_cases[file_name] = data['test_cases']
            except yaml.YAMLError as exc:
                print(exc)
    return test_cases


def state_fixture_mark_fn(fixture_name):
    if fixture_name == 'test_transfer':
        return pytest.mark.skip(reason="has not implemented")
    else:
        return None


@to_tuple
def get_test_cases(fixture_file_names):
    test_cases = get_all_test_cases(fixture_file_names)
    for file_name, test_cases in test_cases.items():
        for test_case in test_cases:
            test_name = test_case['name']
            test_id = f"{file_name}::{test_name}:{test_case.lc.line}"
            mark = state_fixture_mark_fn(test_name)
            if mark is not None:
                yield pytest.param(test_case, id=test_id, marks=(mark,))
            else:
                yield pytest.param(test_case, id=test_id)


all_test_cases = get_test_cases(FIXTURE_FILE_NAMES)


@pytest.mark.parametrize(
    "test_case",
    all_test_cases
)
def test_state(base_db, test_case):
    execute_state_transtion(test_case, base_db)


def generate_config_by_dict(dict_config):
    dict_config['DEPOSIT_CONTRACT_ADDRESS'] = b'\x00' * 20
    for key in list(dict_config):
        if 'DOMAIN_' in key:
            # DOMAIN is defined in SignatureDomain
            dict_config.pop(key, None)
    return Eth2Config(**dict_config)


def execute_state_transtion(test_case, base_db):
    dict_config = test_case['config']
    verify_signatures = test_case['verify_signatures']
    dict_initial_state = test_case['initial_state']
    dict_blocks = test_case['blocks']
    dict_expected_state = test_case['expected_state']

    # TODO: make it case by case
    assert verify_signatures is False

    # Set config
    config = generate_config_by_dict(dict_config)

    # Set Vector fields
    override_vector_lengths(config)

    # Set pre_state
    pre_state = from_formatted_dict(dict_initial_state, BeaconState)

    # Set blocks
    blocks = ()
    for dict_block in dict_blocks:
        block = from_formatted_dict(dict_block, SerenityBeaconBlock)
        blocks += (block,)

    sm_class = SerenityStateMachine.configure(
        __name__='SerenityStateMachineForTesting',
        config=config,
    )
    chaindb = BeaconChainDB(base_db, Eth2GenesisConfig(config))

    post_state = pre_state.copy()
    for block in blocks:
        sm = sm_class(chaindb, None, post_state)
        post_state, _ = sm.import_block(block)

    # Use dict diff, easier to see the diff
    dict_post_state = to_formatted_dict(post_state, BeaconState)

    for key, value in dict_expected_state.items():
        if isinstance(value, list):
            value = tuple(value)
        assert dict_post_state[key] == value
