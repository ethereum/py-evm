import os

import pytest

import rlp

from eth_utils import (
    to_canonical_address,
)

from eth_keys.exceptions import (
    BadSignature,
)

from evm import (
    MainnetChain,
)
from evm.db import (
    get_db_backend,
)
from evm.db.chain import ChainDB

from evm.exceptions import (
    ValidationError,
)
from evm.rlp.headers import (
    BlockHeader,
)

from evm.utils.fixture_tests import (
    generate_fixture_tests,
    load_fixture,
    normalize_transactiontest_fixture,
    normalize_signed_transaction,
)


ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


BASE_FIXTURE_PATH = os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'TransactionTests')


def pytest_generate_tests(metafunc):
    generate_fixture_tests(
        metafunc=metafunc,
        base_fixture_path=BASE_FIXTURE_PATH,
    )


@pytest.fixture
def fixture(fixture_data):
    fixture_path, fixture_key = fixture_data
    fixture = load_fixture(
        fixture_path,
        fixture_key,
        normalize_transactiontest_fixture,
    )
    return fixture


def test_transaction_fixtures(fixture):
    header = BlockHeader(1, fixture['blocknumber'], 100)
    chain = MainnetChain(ChainDB(get_db_backend()), header=header)
    vm = chain.get_vm()
    TransactionClass = vm.get_transaction_class()

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

        try:
            assert transaction.sender == sender
        except BadSignature:
            assert not (27 <= transaction.v <= 34)
    else:
        # check RLP correctness
        try:
            transaction = rlp.decode(fixture['rlp'], sedes=TransactionClass)
        # fixture normalization changes the fixture key from rlp to rlpHex
        except KeyError:
            assert fixture['rlpHex']
            return
        # rlp is a list of bytes when it shouldn't be
        except TypeError as err:
            assert err.args == ("'bytes' object cannot be interpreted as an integer",)
            return
        # rlp is invalid or not in the correct form
        except (rlp.exceptions.ObjectDeserializationError, rlp.exceptions.DecodingError):
            return

        # check parameter correctness
        try:
            transaction.validate()
        except ValidationError:
            return
