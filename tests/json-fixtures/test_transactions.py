import os

import pytest

import rlp

from eth_utils import (
    is_same_address,
    to_tuple,
    ValidationError,
)
from eth.tools.fixtures import (
    generate_fixture_tests,
    load_fixture,
)
from eth.tools._utils.normalization import (
    normalize_transactiontest_fixture,
)
from eth.vm.forks.frontier.transactions import (
    FrontierTransaction
)
from eth.vm.forks.homestead.transactions import (
    HomesteadTransaction
)
from eth.vm.forks.spurious_dragon.transactions import (
    SpuriousDragonTransaction
)
from eth.vm.forks.byzantium.transactions import (
    ByzantiumTransaction
)
from eth.vm.forks.constantinople.transactions import (
    ConstantinopleTransaction
)
from eth.vm.forks.petersburg.transactions import (
    PetersburgTransaction
)
from eth.vm.forks.istanbul.transactions import (
    IstanbulTransaction
)

from eth_typing.enums import (
    ForkName
)


ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


BASE_FIXTURE_PATH = os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'TransactionTests')


# Fixtures have an `_info` key at their root which we need to skip over.
FIXTURE_FORK_SKIPS = {'_info', 'rlp'}


@to_tuple
def expand_fixtures_forks(all_fixtures):
    """
    The transaction fixtures have different definitions for each fork and must be
    expanded one step further to have one fixture for each defined fork within
    the fixture.
    """
    for fixture_path, fixture_key in all_fixtures:
        fixture = load_fixture(fixture_path, fixture_key)
        for fixture_fork, _ in fixture.items():
            if fixture_fork not in FIXTURE_FORK_SKIPS:
                yield fixture_path, fixture_key, fixture_fork


def pytest_generate_tests(metafunc):
    generate_fixture_tests(
        metafunc=metafunc,
        base_fixture_path=BASE_FIXTURE_PATH,
        preprocess_fn=expand_fixtures_forks,
    )


@pytest.fixture
def fixture(fixture_data):
    fixture_path, fixture_key, fixture_fork = fixture_data
    fixture = load_fixture(
        fixture_path,
        fixture_key,
        normalize_transactiontest_fixture(fork=fixture_fork),
    )

    return fixture


@pytest.fixture
def fixture_transaction_class(fixture_data):
    _, _, fork_name = fixture_data
    if fork_name == ForkName.Frontier:
        return FrontierTransaction
    elif fork_name == ForkName.Homestead:
        return HomesteadTransaction
    elif fork_name == ForkName.EIP150:
        return HomesteadTransaction
    elif fork_name == ForkName.EIP158:
        return SpuriousDragonTransaction
    elif fork_name == ForkName.Byzantium:
        return ByzantiumTransaction
    elif fork_name == ForkName.Constantinople:
        return ConstantinopleTransaction
    elif fork_name == ForkName.ConstantinopleFix:
        return PetersburgTransaction
    elif fork_name == ForkName.Istanbul:
        return IstanbulTransaction  # There seem to be no new transaction tests since Istanbul
    elif fork_name == ForkName.Metropolis:
        pytest.skip("Metropolis Transaction class has not been implemented")
    else:
        raise ValueError(f"Unknown Fork Name: {fork_name}")


def test_transaction_fixtures(fixture, fixture_transaction_class):

    TransactionClass = fixture_transaction_class

    try:
        txn = rlp.decode(fixture['rlp'], sedes=TransactionClass)
    except (rlp.DeserializationError, rlp.exceptions.DecodingError):
        assert 'hash' not in fixture, "Transaction was supposed to be valid"
    except TypeError as err:
        # Ensure we are only letting type errors pass that are caused by
        # RLP elements that are lists when they shouldn't be lists
        # (see: /TransactionTests/ttWrongRLP/RLPElementIsListWhenItShouldntBe.json)
        assert err.args == ("'bytes' object cannot be interpreted as an integer",)
        assert 'hash' not in fixture, "Transaction was supposed to be valid"
    # fixture normalization changes the fixture key from rlp to rlpHex
    except KeyError:
        assert fixture['rlpHex']
        assert 'hash' not in fixture, "Transaction was supposed to be valid"
    else:
        # check parameter correctness
        try:
            txn.validate()
        except ValidationError:
            return

    if 'sender' in fixture:
        assert 'hash' in fixture, "Transaction was supposed to be invalid"
        assert is_same_address(txn.sender, fixture['sender'])
