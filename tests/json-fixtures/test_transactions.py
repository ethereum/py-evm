import pytest
import os

from eth_typing.enums import (
    ForkName,
)
from eth_utils import (
    ValidationError,
    is_same_address,
    to_tuple,
)
import rlp

from eth.exceptions import (
    UnrecognizedTransactionType,
)
from eth.tools._utils.normalization import (
    normalize_transactiontest_fixture,
)
from eth.tools.fixtures import (
    filter_fixtures,
    generate_fixture_tests,
    load_fixture,
)
from eth.vm.forks.berlin.constants import (
    VALID_TRANSACTION_TYPES,
)
from eth.vm.forks.berlin.transactions import (
    BerlinTransactionBuilder,
)
from eth.vm.forks.byzantium.transactions import (
    ByzantiumTransaction,
)
from eth.vm.forks.cancun.transactions import (
    CancunTransactionBuilder,
)
from eth.vm.forks.constantinople.transactions import (
    ConstantinopleTransaction,
)
from eth.vm.forks.frontier.transactions import (
    FrontierTransaction,
)
from eth.vm.forks.homestead.transactions import (
    HomesteadTransaction,
)
from eth.vm.forks.istanbul.transactions import (
    IstanbulTransaction,
)
from eth.vm.forks.london.transactions import (
    LondonTransactionBuilder,
)
from eth.vm.forks.paris.transactions import (
    ParisTransactionBuilder,
)
from eth.vm.forks.petersburg.transactions import (
    PetersburgTransaction,
)
from eth.vm.forks.prague.transactions import (
    PragueTransactionBuilder,
)
from eth.vm.forks.shanghai.transactions import (
    ShanghaiTransactionBuilder,
)
from eth.vm.forks.spurious_dragon.transactions import (
    SpuriousDragonTransaction,
)

ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

# tests up to and including Cancun
LEGACY_CANCUN_SNAPSHOT_TESTS = os.path.join(
    ROOT_PROJECT_DIR, "fixtures", "LegacyTests", "Cancun"
)
EEST_TESTS = os.path.join(ROOT_PROJECT_DIR, "fixtures_eest")

# Fixtures have an `_info` key at their root which we need to skip over.
FIXTURE_FORK_SKIPS = {"_info", "txbytes"}


@to_tuple
def expand_fixtures_forks(all_fixtures):
    """
    The transaction fixtures have different definitions for each fork and must be
    expanded one step further to have one fixture for each defined fork within
    the fixture.
    """
    for fixture_path, fixture_key in all_fixtures:
        fixture = load_fixture(fixture_path, fixture_key)

        if "result" in fixture.keys():
            # old transaction tests
            for fixture_fork, _ in fixture["result"].items():
                if fixture_fork not in FIXTURE_FORK_SKIPS:
                    yield fixture_path, fixture_key, fixture_fork

        elif "post" in fixture.keys():
            # txn tests from EEST general state tests
            for fixture_fork, _ in fixture["post"].items():
                yield fixture_path, fixture_key, fixture_fork


def ignore_non_txn_tests(fixture_path, _fixture_name):
    txn_test_paths = [
        "TransactionTests/",
        "GeneralStateTests/",
        "state_tests/",
    ]
    return not any(fixture_path.startswith(path_start) for path_start in txn_test_paths)


def pytest_generate_tests(metafunc):
    generate_fixture_tests(
        metafunc=metafunc,
        base_fixture_paths=[LEGACY_CANCUN_SNAPSHOT_TESTS, EEST_TESTS],
        filter_fn=filter_fixtures(
            fixtures_base_dirs={
                "legacy_tests": LEGACY_CANCUN_SNAPSHOT_TESTS,
                "eest": EEST_TESTS,
            },
            ignore_fn=ignore_non_txn_tests,
        ),
        postprocess_fn=expand_fixtures_forks,
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
    _, test_name, fork_name = fixture_data

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
        return IstanbulTransaction
    elif fork_name == ForkName.Berlin:
        return BerlinTransactionBuilder
    elif fork_name == ForkName.London:
        return LondonTransactionBuilder
    elif fork_name == ForkName.Metropolis:
        pytest.skip("Metropolis Transaction class has not been implemented")
    elif fork_name == ForkName.Paris:
        return ParisTransactionBuilder
    elif fork_name == ForkName.Shanghai:
        return ShanghaiTransactionBuilder
    elif fork_name == ForkName.Cancun:
        return CancunTransactionBuilder
    elif fork_name == ForkName.Prague:
        return PragueTransactionBuilder
    else:
        raise ValueError(f"Unknown Fork Name: {fork_name}")


def test_transaction_fixtures(fixture, fixture_transaction_class):
    TransactionClass = fixture_transaction_class

    try:
        txn = TransactionClass.decode(fixture["txbytes"])
    except (rlp.DeserializationError, rlp.exceptions.DecodingError):
        assert (
            "hash" not in fixture or "expectException" in fixture
        ), "Transaction was supposed to be valid"
    except TypeError as err:
        # Ensure we are only letting type errors pass that are caused by
        # RLP elements that are lists when they shouldn't be lists
        # (see: /TransactionTests/ttWrongRLP/RLPElementIsListWhenItShouldntBe.json)
        assert err.args == ("'bytes' object cannot be interpreted as an integer",)
        assert (
            "hash" not in fixture or "expectException" in fixture
        ), "Transaction was supposed to be valid"
    # fixture normalization changes the fixture key from rlp to rlpHex
    except KeyError:
        assert fixture["rlpHex"]
        assert (
            "hash" not in fixture or "expectException" in fixture
        ), "Transaction was supposed to be valid"
    except ValidationError as err:
        err_matchers = ("Cannot build typed transaction with", ">= 0x80")
        assert all(_ in err.args[0] for _ in err_matchers)
        assert (
            "hash" not in fixture or "expectException" in fixture
        ), "Transaction was supposed to be valid"
    except UnrecognizedTransactionType as err:
        assert err.args[1] == "Unknown transaction type"
        assert hex(err.args[0]) not in VALID_TRANSACTION_TYPES
        assert (
            "hash" not in fixture or "expectException" in fixture
        ), "Transaction was supposed to be valid"
    else:
        # check parameter correctness
        try:
            txn.validate()
        except ValidationError:
            return

    if "sender" in fixture:
        assert "hash" in fixture, "Transaction was supposed to be invalid"
        assert is_same_address(txn.sender, fixture["sender"])
