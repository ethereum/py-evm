import os
import pytest
import rlp

from eth.exceptions import (
    ValidationError,
)

from eth.rlp.headers import (
    BlockHeader,
)

from eth.tools.fixture_tests import (
    apply_fixture_block_to_chain,
    new_chain_from_fixture,
    genesis_params_from_fixture,
    load_fixture,
    generate_fixture_tests,
    filter_fixtures,
    normalize_blockchain_fixtures,
    verify_account_db,
    assert_rlp_equal,
)


ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


BASE_FIXTURE_PATH = os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'BlockchainTests')


def blockchain_fixture_mark_fn(fixture_path, fixture_name):
    if fixture_path.startswith('bcExploitTest'):
        return pytest.mark.skip("Exploit tests are slow")
    elif fixture_path == 'bcWalletTest/walletReorganizeOwners.json':
        return pytest.mark.skip("Wallet owner reorganization tests are slow")


def blockchain_fixture_ignore_fn(fixture_path, fixture_name):
    if fixture_path.startswith('GeneralStateTests'):
        # General state tests are also exported as blockchain tests.  We
        # skip them here so we don't run them twice"
        return True


def pytest_generate_tests(metafunc):
    generate_fixture_tests(
        metafunc=metafunc,
        base_fixture_path=BASE_FIXTURE_PATH,
        filter_fn=filter_fixtures(
            fixtures_base_dir=BASE_FIXTURE_PATH,
            mark_fn=blockchain_fixture_mark_fn,
            ignore_fn=blockchain_fixture_ignore_fn,
        ),
    )


@pytest.fixture
def fixture(fixture_data):
    fixture_path, fixture_key = fixture_data
    fixture = load_fixture(
        fixture_path,
        fixture_key,
        normalize_blockchain_fixtures,
    )
    if fixture['network'] == 'Constantinople':
        pytest.skip('Constantinople VM rules not yet supported')
    return fixture


def test_blockchain_fixtures(fixture_data, fixture):
    try:
        chain = new_chain_from_fixture(fixture)
    except ValueError as e:
        raise AssertionError("could not load chain for %r" % fixture_data) from e

    genesis_params = genesis_params_from_fixture(fixture)
    expected_genesis_header = BlockHeader(**genesis_params)

    # TODO: find out if this is supposed to pass?
    # if 'genesisRLP' in fixture:
    #     assert rlp.encode(genesis_header) == fixture['genesisRLP']

    genesis_block = chain.get_canonical_block_by_number(0)
    genesis_header = genesis_block.header

    assert_rlp_equal(genesis_header, expected_genesis_header)

    # 1 - mine the genesis block
    # 2 - loop over blocks:
    #     - apply transactions
    #     - mine block
    # 4 - profit!!

    for block_fixture in fixture['blocks']:
        should_be_good_block = 'blockHeader' in block_fixture

        if 'rlp_error' in block_fixture:
            assert not should_be_good_block
            continue

        if should_be_good_block:
            (block, mined_block, block_rlp) = apply_fixture_block_to_chain(block_fixture, chain)
            assert_rlp_equal(block, mined_block)
        else:
            try:
                apply_fixture_block_to_chain(block_fixture, chain)
            except (TypeError, rlp.DecodingError, rlp.DeserializationError, ValidationError) as err:
                # failure is expected on this bad block
                pass
            else:
                raise AssertionError("Block should have caused a validation error")

    latest_block_hash = chain.get_canonical_block_by_number(chain.get_block().number - 1).hash
    assert latest_block_hash == fixture['lastblockhash']

    verify_account_db(fixture['postState'], chain.get_vm().state.account_db)
