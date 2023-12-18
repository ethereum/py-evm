import os

from eth_typing.enums import (
    ForkName,
)
from eth_utils import (
    to_int,
)
import pytest

from eth.constants import (
    EMPTY_UNCLE_HASH,
)
from eth.rlp.headers import (
    BlockHeader,
)
from eth.tools.fixtures import (
    filter_fixtures,
    generate_fixture_tests,
    load_fixture,
)
from eth.vm.forks import (
    ArrowGlacierVM,
    BerlinVM,
    ByzantiumVM,
    ConstantinopleVM,
    FrontierVM,
    GrayGlacierVM,
    HomesteadVM,
)

ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

BASE_FIXTURE_PATH = os.path.join(
    ROOT_PROJECT_DIR,
    "fixtures",
    "DifficultyTests",
)


def pytest_generate_tests(metafunc):
    generate_fixture_tests(
        metafunc=metafunc,
        base_fixture_path=BASE_FIXTURE_PATH,
        filter_fn=filter_fixtures(
            fixtures_base_dir=BASE_FIXTURE_PATH,
        ),
    )


@pytest.fixture
def fixture(fixture_data):
    fixture_path, fixture_key = fixture_data
    fixture = load_fixture(
        fixture_path,
        fixture_key,
    )
    return fixture


VM_FORK_MAP = {
    ForkName.Frontier: FrontierVM,
    ForkName.Homestead: HomesteadVM,
    ForkName.Byzantium: ByzantiumVM,
    ForkName.Constantinople: ConstantinopleVM,
    ForkName.Berlin: BerlinVM,
    ForkName.ArrowGlacier: ArrowGlacierVM,
    ForkName.GrayGlacier: GrayGlacierVM,
}


def test_difficulty_fixtures(fixture):
    fork_name = list(fixture.keys())[1]

    if fork_name not in VM_FORK_MAP.keys():
        raise NotImplementedError(
            f"VM_FORK_MAP needs to be updated to support {fork_name}."
        )

    vm = VM_FORK_MAP[fork_name]

    fixture_payload = fixture[fork_name].items()

    for _, test_payload in fixture_payload:
        formatted_test_payload = {
            # hexstr -> int for all values in test_payload
            k: to_int(hexstr=v)
            for k, v in test_payload.items()
        }

        parent_uncle_hash = (
            # 'parentUncles' are either 0 or 1, depending on whether the parent has
            # uncles or not. Therefore, use EMPTY_UNCLE_HASH when 0 and non-empty
            # hash when 1.
            EMPTY_UNCLE_HASH
            if formatted_test_payload["parentUncles"] == 0
            else "0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347"
        )

        current_block_number = formatted_test_payload["currentBlockNumber"]

        parent_header = BlockHeader(
            difficulty=formatted_test_payload["parentDifficulty"],
            block_number=current_block_number - 1,
            timestamp=formatted_test_payload["parentTimestamp"],
            uncles_hash=parent_uncle_hash,
            gas_limit=0,  # necessary for instantiation but arbitrary for this test
        )

        # calculate the current difficulty using the parent header
        difficulty = vm.compute_difficulty(
            parent_header=parent_header,
            timestamp=formatted_test_payload["currentTimestamp"],
        )

        assert difficulty == formatted_test_payload["currentDifficulty"]
