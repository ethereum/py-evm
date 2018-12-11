import os
import pytest
import rlp

from eth_utils import (
    to_tuple,
    ValidationError,
)

from eth.rlp.headers import (
    BlockHeader,
)

from eth.tools.rlp import (
    assert_imported_genesis_header_unchanged,
    assert_mined_block_unchanged,
)
from eth.tools._utils.normalization import (
    normalize_blockchain_fixtures,
)
from eth.tools.fixtures import (
    apply_fixture_block_to_chain,
    filter_fixtures,
    generate_fixture_tests,
    genesis_params_from_fixture,
    load_fixture,
    new_chain_from_fixture,
    verify_account_db,
)


ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


BASE_FIXTURE_PATH = os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'BlockchainTests')


# These are the slowest 50 tests from the full statetest run.  This list should
# be regenerated occasionally using `--durations 50`.
SLOWEST_TESTS = {
    ('stStaticCall/static_Call50000_sha256.json', 'static_Call50000_sha256'),
    ('stStaticCall/static_Call50000_rip160.json', 'static_Call50000_rip160'),
    ('stStaticCall/static_Call50000_sha256.json', 'static_Call50000_sha256'),
    ('stStaticCall/static_Call50000.json', 'static_Call50000'),
    ('stStaticCall/static_Call50000_ecrec.json', 'static_Call50000_ecrec'),
    ('stStaticCall/static_Call50000_rip160.json', 'static_Call50000_rip160'),
    ('stStaticCall/static_LoopCallsThenRevert.json', 'static_LoopCallsThenRevert'),
    ('stStaticCall/static_Call50000_identity2.json', 'static_Call50000_identity2'),
    ('stStaticCall/static_Call50000_identity.json', 'static_Call50000_identity'),
    ('stStaticCall/static_Return50000_2.json', 'static_Return50000_2'),
    ('stCallCreateCallCodeTest/Call1024PreCalls.json', 'Call1024PreCalls'),
    ('stChangedEIP150/Call1024PreCalls.json', 'Call1024PreCalls'),
    ('stDelegatecallTestHomestead/Call1024PreCalls.json', 'Call1024PreCalls'),
    ('stStaticCall/static_Call50000.json', 'static_Call50000'),
    ('stStaticCall/static_Call50000_ecrec.json', 'static_Call50000_ecrec'),
    ('stStaticCall/static_Call1024PreCalls2.json', 'static_Call1024PreCalls2'),
    ('stStaticCall/static_Call50000_identity.json', 'static_Call50000_identity'),
    ('stStaticCall/static_Call50000_identity2.json', 'static_Call50000_identity2'),
    ('stStaticCall/static_LoopCallsThenRevert.json', 'static_LoopCallsThenRevert'),
    ('stCallCreateCallCodeTest/Call1024BalanceTooLow.json', 'Call1024BalanceTooLow'),  # noqa: E501
    ('stChangedEIP150/Call1024BalanceTooLow.json', 'Call1024BalanceTooLow'),
    ('stCallCreateCallCodeTest/Callcode1024BalanceTooLow.json', 'Callcode1024BalanceTooLow'),  # noqa: E501
    ('stChangedEIP150/Callcode1024BalanceTooLow.json', 'Callcode1024BalanceTooLow'),  # noqa: E501
    ('stSystemOperationsTest/CallRecursiveBomb0_OOG_atMaxCallDepth.json', 'CallRecursiveBomb0_OOG_atMaxCallDepth'),  # noqa: E501
    ('stRevertTest/LoopCallsDepthThenRevert2.json', 'LoopCallsDepthThenRevert2'),
    ('stRevertTest/LoopCallsDepthThenRevert3.json', 'LoopCallsDepthThenRevert3'),
    ('stDelegatecallTestHomestead/CallRecursiveBombPreCall.json', 'CallRecursiveBombPreCall'),  # noqa: E501
    ('stRevertTest/LoopCallsThenRevert.json', 'LoopCallsThenRevert'),
    ('stCallCreateCallCodeTest/CallRecursiveBombPreCall.json', 'CallRecursiveBombPreCall'),  # noqa: E501
    ('stStaticCall/static_Call50000bytesContract50_1.json', 'static_Call50000bytesContract50_1'),  # noqa: E501
    ('stStaticCall/static_Call1024PreCalls.json', 'static_Call1024PreCalls'),
    ('stDelegatecallTestHomestead/Call1024BalanceTooLow.json', 'Call1024BalanceTooLow'),  # noqa: E501
    ('stDelegatecallTestHomestead/Delegatecall1024.json', 'Delegatecall1024'),
    ('stRevertTest/LoopCallsThenRevert.json', 'LoopCallsThenRevert'),
    ('stStaticCall/static_Call50000bytesContract50_2.json', 'static_Call50000bytesContract50_2'),  # noqa: E501
    ('stStaticCall/static_Call1024PreCalls2.json', 'static_Call1024PreCalls2'),
    ('stRandom/randomStatetest636.json', 'randomStatetest636'),
    ('stStaticCall/static_Call1024PreCalls3.json', 'static_Call1024PreCalls3'),
    ('stRandom/randomStatetest467.json', 'randomStatetest467'),
    ('stRandom/randomStatetest458.json', 'randomStatetest458'),
    ('stRandom/randomStatetest150.json', 'randomStatetest150'),
    ('stRandom/randomStatetest639.json', 'randomStatetest639'),
    ('stStaticCall/static_LoopCallsDepthThenRevert2.json', 'static_LoopCallsDepthThenRevert2'),  # noqa: E501
    ('stRandom/randomStatetest154.json', 'randomStatetest154'),
    ('stRecursiveCreate/recursiveCreateReturnValue.json', 'recursiveCreateReturnValue'),  # noqa: E501
    ('stStaticCall/static_LoopCallsDepthThenRevert3.json', 'static_LoopCallsDepthThenRevert3'),  # noqa: E501
    ('stSystemOperationsTest/ABAcalls1.json', 'ABAcalls1'),
    ('stSpecialTest/failed_tx_xcf416c53.json', 'failed_tx_xcf416c53'),
    ('stRandom/randomStatetest159.json', 'randomStatetest159'),
    ('stRandom/randomStatetest554.json', 'randomStatetest554'),
}


# These are tests that are thought to be incorrect or buggy upstream,
# at the commit currently checked out in submodule `fixtures`.
# Ideally, this list should be empty.
# WHEN ADDING ENTRIES, ALWAYS PROVIDE AN EXPLANATION!
INCORRECT_UPSTREAM_TESTS = {
    # The test considers a "synthetic" scenario (the state described there can't
    # be arrived at using regular consensus rules).
    # * https://github.com/ethereum/py-evm/pull/1224#issuecomment-418775512
    # The result is in conflict with the yellow-paper:
    # * https://github.com/ethereum/py-evm/pull/1224#issuecomment-418800369
    ('GeneralStateTests/stRevertTest/RevertInCreateInInit_d0g0v0.json', 'RevertInCreateInInit_d0g0v0_Byzantium'),  # noqa: E501
}


def blockchain_fixture_mark_fn(fixture_path, fixture_name, fixture_fork):
    fixture_id = (fixture_path, fixture_name)

    if fixture_path.startswith('bcExploitTest'):
        return pytest.mark.skip("Exploit tests are slow")
    elif fixture_path == 'bcWalletTest/walletReorganizeOwners.json':
        return pytest.mark.skip("Wallet owner reorganization tests are slow")
    elif fixture_id in INCORRECT_UPSTREAM_TESTS:
        return pytest.mark.xfail(reason="Listed in INCORRECT_UPSTREAM_TESTS.")
    elif 'stTransactionTest/zeroSigTransa' in fixture_path:
        return pytest.mark.skip("EIP-86 not supported.")
    elif fixture_id in SLOWEST_TESTS:
        if should_run_slow_tests():
            return
        else:
            return pytest.mark.skip("Skipping slow test")
    elif 'stQuadraticComplexityTest' in fixture_path:
        return pytest.mark.skip("Skipping slow test")


def generate_ignore_fn_for_fork(passed_fork):
    if passed_fork:
        passed_fork = passed_fork.lower()

        def ignore_fn(fixture_path, fixture_key, fixture_fork):
            return fixture_fork.lower() != passed_fork

        return ignore_fn


@to_tuple
def expand_fixtures_forks(all_fixtures):
    for fixture_path, fixture_key in all_fixtures:
        fixture = load_fixture(fixture_path, fixture_key)
        yield fixture_path, fixture_key, fixture['network']


def pytest_generate_tests(metafunc):
    fork = metafunc.config.getoption('fork')
    generate_fixture_tests(
        metafunc=metafunc,
        base_fixture_path=BASE_FIXTURE_PATH,
        preprocess_fn=expand_fixtures_forks,
        filter_fn=filter_fixtures(
            fixtures_base_dir=BASE_FIXTURE_PATH,
            mark_fn=blockchain_fixture_mark_fn,
            ignore_fn=generate_ignore_fn_for_fork(fork)
        ),
    )


@pytest.fixture
def fixture(fixture_data):
    fixture_path, fixture_key, fixture_fork = fixture_data
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

    assert_imported_genesis_header_unchanged(expected_genesis_header, genesis_header)

    # 1 - mine the genesis block
    # 2 - loop over blocks:
    #     - apply transactions
    #     - mine block
    # 3 - diff resulting state with expected state
    # 4 - check that all previous blocks were valid

    mined_blocks = list()
    for block_fixture in fixture['blocks']:
        should_be_good_block = 'blockHeader' in block_fixture

        if 'rlp_error' in block_fixture:
            assert not should_be_good_block
            continue

        if should_be_good_block:
            (block, mined_block, block_rlp) = apply_fixture_block_to_chain(
                block_fixture,
                chain,
                perform_validation=False  # we manually validate below
            )
            mined_blocks.append((block, mined_block))
        else:
            try:
                apply_fixture_block_to_chain(block_fixture, chain)
            except (TypeError, rlp.DecodingError, rlp.DeserializationError, ValidationError) as err:
                # failure is expected on this bad block
                pass
            else:
                raise AssertionError("Block should have caused a validation error")

    latest_block_hash = chain.get_canonical_block_by_number(chain.get_block().number - 1).hash
    if latest_block_hash != fixture['lastblockhash']:
        verify_account_db(fixture['postState'], chain.get_vm().state.account_db)
        assert False, 'the state must be different if the hashes are'

    for block, mined_block in mined_blocks:
        assert_mined_block_unchanged(block, mined_block)
        chain.validate_block(block)
