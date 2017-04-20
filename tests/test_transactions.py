import pytest

import rlp

import json
import os

from trie.db.memory import (
    MemoryDB,
)

from eth_utils import (
    keccak,
)

from evm.exceptions import (
    InvalidTransaction,
)
from evm.vm.flavors import (
    MainnetEVM,
)

from evm.utils.fixture_tests import (
    recursive_find_files,
    normalize_transactiontest_fixture,
)


ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(__file__))


BASE_FIXTURE_PATH = os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'TransactionTests')
#HOMESTEAD_FIXTURE_PATH = os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'TransactionTests', 'Homestead')


#FIXTURES_PATHS = tuple(recursive_find_files(BASE_FIXTURE_PATH, "*.json"))
#FIXTURES_PATHS = tuple(recursive_find_files(HOMESTEAD_FIXTURE_PATH, "*.json"))
FIXTURES_PATHS = (
    os.path.join(BASE_FIXTURE_PATH, "ttTransactionTest.json"),
)


RAW_FIXTURES = tuple(
    (
        os.path.relpath(fixture_path, BASE_FIXTURE_PATH),
        json.load(open(fixture_path)),
    )
    for fixture_path in FIXTURES_PATHS
)


FIXTURES = tuple(
    (
        "{0}:{1}".format(fixture_filename, key),
        normalize_transactiontest_fixture(fixtures[key]),
    )
    for fixture_filename, fixtures in RAW_FIXTURES
    for key in sorted(fixtures.keys())
    if 'post' in fixtures[key]
)


@pytest.mark.parametrize(
    'fixture_name,fixture', FIXTURES,
)
def test_vm_success_using_fixture(fixture_name, fixture):
    EVM = MainnetEVM.get_evm_class_for_block_number(fixture['blocknumber'])

    assert False, "TODO"
