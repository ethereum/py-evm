from dataclasses import dataclass
from typing import Tuple

from eth_utils import decode_hex
import pytest

from eth2.beacon.committee_helpers import compute_shuffled_index
from eth2.beacon.tools.fixtures.config_name import ONLY_MINIMAL
from eth2.beacon.tools.fixtures.test_case import BaseTestCase
from eth2.beacon.tools.misc.ssz_vector import override_lengths
from tests.eth2.fixtures.helpers import get_test_cases
from tests.eth2.fixtures.path import BASE_FIXTURE_PATH, ROOT_PROJECT_DIR

# Test files
SHUFFLING_FIXTURE_PATH = BASE_FIXTURE_PATH / "shuffling"
FIXTURE_PATHES = (SHUFFLING_FIXTURE_PATH,)
FILTERED_CONFIG_NAMES = ONLY_MINIMAL


@dataclass
class ShufflingTestCase(BaseTestCase):
    seed: bytes
    count: int
    shuffled: Tuple[int, ...]


#
# Helpers for generating test suite
#
def parse_shuffling_test_case(test_case, handler, index, config):
    override_lengths(config)

    return ShufflingTestCase(
        handler=handler,
        index=index,
        seed=decode_hex(test_case["seed"]),
        count=test_case["count"],
        shuffled=tuple(test_case["shuffled"]),
    )


all_test_cases = get_test_cases(
    root_project_dir=ROOT_PROJECT_DIR,
    fixture_pathes=FIXTURE_PATHES,
    config_names=FILTERED_CONFIG_NAMES,
    parse_test_case_fn=parse_shuffling_test_case,
)


@pytest.mark.parametrize("test_case, config", all_test_cases)
def test_shuffling_fixture(test_case, config):

    result = tuple(
        compute_shuffled_index(
            index, test_case.count, test_case.seed, config.SHUFFLE_ROUND_COUNT
        )
        for index in range(test_case.count)
    )
    assert result == test_case.shuffled
