import pytest

from eth_utils import (
    to_tuple,
)
from eth2.beacon.tools.fixtures.loading import (
    get_all_test_files,
)


#
# pytest setting
#
def bls_setting_mark_fn(bls_setting):
    if bls_setting is True:
        return pytest.mark.noautofixture
    return None


@to_tuple
def get_test_cases(root_project_dir, fixture_pathes, parse_test_case_fn):
    # TODO: batch reading files
    test_files = get_all_test_files(
        root_project_dir,
        fixture_pathes,
        parse_test_case_fn=parse_test_case_fn,
    )
    for test_file in test_files:
        for test_case in test_file.test_cases:
            yield mark_test_case(test_file, test_case)


def mark_test_case(test_file, test_case):
    test_id = f"{test_file.file_name}::{test_case.description}:{test_case.line_number}"
    mark = bls_setting_mark_fn(test_case.bls_setting)
    if mark is not None:
        return pytest.param(test_case, test_file.config, id=test_id, marks=(mark,))
    else:
        return pytest.param(test_case, test_file.config, id=test_id)
