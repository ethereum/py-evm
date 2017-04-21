import pytest

import rlp

from eth_utils import (
    to_canonical_address,
)

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
    ValidationError,
    InvalidSignature,
)
from evm.vm.flavors import (
    MainnetEVM,
)

from evm.utils.fixture_tests import (
    recursive_find_files,
    normalize_transactiontest_fixture,
    normalize_signed_transaction,
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
)


@pytest.mark.parametrize(
    'fixture_name,fixture', FIXTURES,
)
def test_transaction_class(fixture_name, fixture):
    EVM = MainnetEVM.get_evm_class_for_block_number(fixture['blocknumber'])
    TransactionClass = EVM.get_transaction_class()

    if 'sender' in fixture:
        transaction = rlp.decode(fixture['rlp'], sedes=TransactionClass)
        expected = normalize_signed_transaction(fixture['transaction'])

        assert transaction.nonce == expected['nonce']
        assert transaction.gas_price == expected['gasPrice']
        assert transaction.gas == expected['gasLimit']
        assert transaction.to == expected['to']
        assert transaction.value == expected['value']
        assert transaction.data == expected['data']
        assert transaction.v == expected['v']
        assert transaction.r == expected['r']
        assert transaction.s == expected['s']

        sender = to_canonical_address(fixture['sender'])

        assert transaction.sender == sender
        assert transaction.hash == fixture['hash']
    else:
        # check RLP correctness
        try:
            transaction = rlp.decode(fixture['rlp'], sedes=TransactionClass)
        except rlp.exceptions.ObjectDeserializationError:
            return

        # check parameter correctness
        try:
            transaction.validate()
        except ValidationError:
            return
