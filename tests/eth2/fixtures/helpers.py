from eth_utils import to_tuple
import pytest

from eth2.beacon.db.chain import BeaconChainDB
from eth2.beacon.state_machines.forks.serenity import SerenityStateMachine
from eth2.beacon.tools.fixtures.loading import get_all_test_files
from eth2.configs import Eth2GenesisConfig


#
# pytest setting
#
def bls_setting_mark_fn(bls_setting):
    if bls_setting:
        return pytest.mark.noautofixture
    return None


@to_tuple
def get_test_cases(root_project_dir, fixture_pathes, config_names, parse_test_case_fn):
    # TODO: batch reading files
    test_files = get_all_test_files(
        root_project_dir, fixture_pathes, config_names, parse_test_case_fn
    )
    for test_file in test_files:
        for test_case in test_file.test_cases:
            bls_setting = (
                test_case.bls_setting if hasattr(test_case, "bls_setting") else False
            )
            yield mark_test_case(test_file, test_case, bls_setting=bls_setting)


def get_test_id(test_file, test_case):
    description = test_case.description if hasattr(test_case, "description") else ""
    return f"{test_file.file_name}:{test_case.index}:{description}"


def mark_test_case(test_file, test_case, bls_setting=False):
    test_id = get_test_id(test_file, test_case)

    mark = bls_setting_mark_fn(bls_setting)
    if mark:
        return pytest.param(test_case, test_file.config, id=test_id, marks=(mark,))
    else:
        return pytest.param(test_case, test_file.config, id=test_id)


#
# State execution
#
def get_sm_class_of_config(config):
    return SerenityStateMachine.configure(
        __name__="SerenityStateMachineForTesting", config=config
    )


def get_chaindb_of_config(base_db, config):
    return BeaconChainDB(base_db, Eth2GenesisConfig(config))
