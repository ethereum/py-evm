import logging
import os

import pytest

from eth_keys import keys

from eth_utils import (
    to_bytes,
    to_tuple,
    ValidationError,
)

from eth_hash.auto import keccak

from eth_typing.enums import (
    ForkName
)


from eth.db import (
    get_db_backend,
)
from eth.db.chain import ChainDB
from eth.vm.forks import (
    TangerineWhistleVM,
    FrontierVM,
    HomesteadVM,
    SpuriousDragonVM,
    ByzantiumVM,
)
from eth.vm.forks.tangerine_whistle.state import TangerineWhistleState
from eth.vm.forks.frontier.state import FrontierState
from eth.vm.forks.homestead.state import HomesteadState
from eth.vm.forks.spurious_dragon.state import SpuriousDragonState
from eth.vm.forks.byzantium.state import ByzantiumState

from eth.rlp.headers import (
    BlockHeader,
)
from eth.tools._utils.hashing import (
    hash_log_entries,
)
from eth.tools.fixtures import (
    filter_fixtures,
    generate_fixture_tests,
    load_fixture,
    normalize_statetest_fixture,
    should_run_slow_tests,
)
from eth.utils.db import (
    apply_state_dict,
)


ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


BASE_FIXTURE_PATH = os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'GeneralStateTests')


logger = logging.getLogger('eth.tests.fixtures.GeneralStateTests')


@to_tuple
def expand_fixtures_forks(all_fixtures):
    """
    The statetest fixtures have different definitions for each fork and must be
    expanded one step further to have one fixture for each defined fork within
    the fixture.
    """

    for fixture_path, fixture_key in all_fixtures:
        fixture = load_fixture(fixture_path, fixture_key)
        for fixture_fork, post_states in sorted(fixture['post'].items()):
            for post_state_index in range(len(post_states)):
                yield fixture_path, fixture_key, fixture_fork, post_state_index


# These are the slowest 50 tests from the full statetest run.  This list should
# be regenerated occasionally using `--durations 50`.
SLOWEST_TESTS = {
    ('stStaticCall/static_Call50000_sha256.json', 'static_Call50000_sha256', 'Byzantium', 0),
    ('stStaticCall/static_Call50000_rip160.json', 'static_Call50000_rip160', 'Byzantium', 0),
    ('stStaticCall/static_Call50000_sha256.json', 'static_Call50000_sha256', 'Byzantium', 1),
    ('stStaticCall/static_Call50000.json', 'static_Call50000', 'Byzantium', 1),
    ('stStaticCall/static_Call50000_ecrec.json', 'static_Call50000_ecrec', 'Byzantium', 1),
    ('stStaticCall/static_Call50000_rip160.json', 'static_Call50000_rip160', 'Byzantium', 1),
    ('stStaticCall/static_LoopCallsThenRevert.json', 'static_LoopCallsThenRevert', 'Byzantium', 0),
    ('stStaticCall/static_Call50000_identity2.json', 'static_Call50000_identity2', 'Byzantium', 1),
    ('stStaticCall/static_Call50000_identity.json', 'static_Call50000_identity', 'Byzantium', 1),
    ('stStaticCall/static_Return50000_2.json', 'static_Return50000_2', 'Byzantium', 0),
    ('stCallCreateCallCodeTest/Call1024PreCalls.json', 'Call1024PreCalls', 'Byzantium', 0),
    ('stChangedEIP150/Call1024PreCalls.json', 'Call1024PreCalls', 'Byzantium', 0),
    ('stDelegatecallTestHomestead/Call1024PreCalls.json', 'Call1024PreCalls', 'Byzantium', 0),
    ('stStaticCall/static_Call50000.json', 'static_Call50000', 'Byzantium', 0),
    ('stStaticCall/static_Call50000_ecrec.json', 'static_Call50000_ecrec', 'Byzantium', 0),
    ('stStaticCall/static_Call1024PreCalls2.json', 'static_Call1024PreCalls2', 'Byzantium', 0),
    ('stStaticCall/static_Call50000_identity.json', 'static_Call50000_identity', 'Byzantium', 0),
    ('stStaticCall/static_Call50000_identity2.json', 'static_Call50000_identity2', 'Byzantium', 0),
    ('stStaticCall/static_LoopCallsThenRevert.json', 'static_LoopCallsThenRevert', 'Byzantium', 1),
    ('stCallCreateCallCodeTest/Call1024BalanceTooLow.json', 'Call1024BalanceTooLow', 'Byzantium', 0),  # noqa: E501
    ('stChangedEIP150/Call1024BalanceTooLow.json', 'Call1024BalanceTooLow', 'Byzantium', 0),
    ('stCallCreateCallCodeTest/Callcode1024BalanceTooLow.json', 'Callcode1024BalanceTooLow', 'Byzantium', 0),  # noqa: E501
    ('stChangedEIP150/Callcode1024BalanceTooLow.json', 'Callcode1024BalanceTooLow', 'Byzantium', 0),  # noqa: E501
    ('stSystemOperationsTest/CallRecursiveBomb0_OOG_atMaxCallDepth.json', 'CallRecursiveBomb0_OOG_atMaxCallDepth', 'Byzantium', 0),  # noqa: E501
    ('stRevertTest/LoopCallsDepthThenRevert2.json', 'LoopCallsDepthThenRevert2', 'Byzantium', 0),
    ('stRevertTest/LoopCallsDepthThenRevert3.json', 'LoopCallsDepthThenRevert3', 'Byzantium', 0),
    ('stDelegatecallTestHomestead/CallRecursiveBombPreCall.json', 'CallRecursiveBombPreCall', 'Byzantium', 0),  # noqa: E501
    ('stRevertTest/LoopCallsThenRevert.json', 'LoopCallsThenRevert', 'Byzantium', 0),
    ('stCallCreateCallCodeTest/CallRecursiveBombPreCall.json', 'CallRecursiveBombPreCall', 'Byzantium', 0),  # noqa: E501
    ('stStaticCall/static_Call50000bytesContract50_1.json', 'static_Call50000bytesContract50_1', 'Byzantium', 1),  # noqa: E501
    ('stStaticCall/static_Call1024PreCalls.json', 'static_Call1024PreCalls', 'Byzantium', 1),
    ('stDelegatecallTestHomestead/Call1024BalanceTooLow.json', 'Call1024BalanceTooLow', 'Byzantium', 0),  # noqa: E501
    ('stDelegatecallTestHomestead/Delegatecall1024.json', 'Delegatecall1024', 'Byzantium', 0),
    ('stRevertTest/LoopCallsThenRevert.json', 'LoopCallsThenRevert', 'Byzantium', 1),
    ('stStaticCall/static_Call50000bytesContract50_2.json', 'static_Call50000bytesContract50_2', 'Byzantium', 1),  # noqa: E501
    ('stStaticCall/static_Call1024PreCalls2.json', 'static_Call1024PreCalls2', 'Byzantium', 1),
    ('stRandom/randomStatetest636.json', 'randomStatetest636', 'Byzantium', 0),
    ('stStaticCall/static_Call1024PreCalls3.json', 'static_Call1024PreCalls3', 'Byzantium', 1),
    ('stRandom/randomStatetest467.json', 'randomStatetest467', 'Byzantium', 0),
    ('stRandom/randomStatetest458.json', 'randomStatetest458', 'Byzantium', 0),
    ('stRandom/randomStatetest150.json', 'randomStatetest150', 'Byzantium', 0),
    ('stRandom/randomStatetest639.json', 'randomStatetest639', 'Byzantium', 0),
    ('stStaticCall/static_LoopCallsDepthThenRevert2.json', 'static_LoopCallsDepthThenRevert2', 'Byzantium', 0),  # noqa: E501
    ('stRandom/randomStatetest154.json', 'randomStatetest154', 'Byzantium', 0),
    ('stRecursiveCreate/recursiveCreateReturnValue.json', 'recursiveCreateReturnValue', 'Byzantium', 0),  # noqa: E501
    ('stStaticCall/static_LoopCallsDepthThenRevert3.json', 'static_LoopCallsDepthThenRevert3', 'Byzantium', 0),  # noqa: E501
    ('stSystemOperationsTest/ABAcalls1.json', 'ABAcalls1', 'Byzantium', 0),
    ('stSpecialTest/failed_tx_xcf416c53.json', 'failed_tx_xcf416c53', 'Byzantium', 0),
    ('stRandom/randomStatetest159.json', 'randomStatetest159', 'Byzantium', 0),
    ('stRandom/randomStatetest554.json', 'randomStatetest554', 'Byzantium', 0),
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
    ('stRevertTest/RevertInCreateInInit.json', 'RevertInCreateInInit', 'Byzantium', 0),
}


def mark_statetest_fixtures(fixture_path, fixture_key, fixture_fork, fixture_index):
    fixture_id = (fixture_path, fixture_key, fixture_fork, fixture_index)
    if fixture_path.startswith('stTransactionTest/zeroSigTransa'):
        return pytest.mark.skip("EIP-86 not supported.")
    elif fixture_id in SLOWEST_TESTS:
        if should_run_slow_tests():
            return
        else:
            return pytest.mark.skip("Skipping slow test")
    elif fixture_path.startswith('stQuadraticComplexityTest'):
        return pytest.mark.skip("Skipping slow test")
    elif fixture_id in INCORRECT_UPSTREAM_TESTS:
        return pytest.mark.xfail(reason="Listed in INCORRECT_UPSTREAM_TESTS.")


def pytest_generate_tests(metafunc):
    generate_fixture_tests(
        metafunc=metafunc,
        base_fixture_path=BASE_FIXTURE_PATH,
        preprocess_fn=expand_fixtures_forks,
        filter_fn=filter_fixtures(
            fixtures_base_dir=BASE_FIXTURE_PATH,
            mark_fn=mark_statetest_fixtures,
        ),
    )


@pytest.fixture
def fixture(fixture_data):
    fixture_path, fixture_key, fixture_fork, post_state_index = fixture_data
    fixture = load_fixture(
        fixture_path,
        fixture_key,
        normalize_statetest_fixture(fork=fixture_fork, post_state_index=post_state_index),
    )
    return fixture


#
# Test Chain Setup
#
def get_block_hash_for_testing(self, block_number):
    if block_number >= self.block_number:
        return b''
    elif block_number < 0:
        return b''
    elif block_number < self.block_number - 256:
        return b''
    else:
        return keccak(to_bytes(text="{0}".format(block_number)))


def get_prev_hashes_testing(self, last_block_hash, db):
    prev_hashes = []
    return prev_hashes


FrontierStateForTesting = FrontierState.configure(
    __name__='FrontierStateForTesting',
    get_ancestor_hash=get_block_hash_for_testing,
)
HomesteadStateForTesting = HomesteadState.configure(
    __name__='HomesteadStateForTesting',
    get_ancestor_hash=get_block_hash_for_testing,
)
TangerineWhistleStateForTesting = TangerineWhistleState.configure(
    __name__='TangerineWhistleStateForTesting',
    get_ancestor_hash=get_block_hash_for_testing,
)
SpuriousDragonStateForTesting = SpuriousDragonState.configure(
    __name__='SpuriousDragonStateForTesting',
    get_ancestor_hash=get_block_hash_for_testing,
)
ByzantiumStateForTesting = ByzantiumState.configure(
    __name__='ByzantiumStateForTesting',
    get_ancestor_hash=get_block_hash_for_testing,
)

FrontierVMForTesting = FrontierVM.configure(
    __name__='FrontierVMForTesting',
    _state_class=FrontierStateForTesting,
    get_prev_hashes=get_prev_hashes_testing,
)
HomesteadVMForTesting = HomesteadVM.configure(
    __name__='HomesteadVMForTesting',
    _state_class=HomesteadStateForTesting,
    get_prev_hashes=get_prev_hashes_testing,
)
TangerineWhistleVMForTesting = TangerineWhistleVM.configure(
    __name__='TangerineWhistleVMForTesting',
    _state_class=TangerineWhistleStateForTesting,
    get_prev_hashes=get_prev_hashes_testing,
)
SpuriousDragonVMForTesting = SpuriousDragonVM.configure(
    __name__='SpuriousDragonVMForTesting',
    _state_class=SpuriousDragonStateForTesting,
    get_prev_hashes=get_prev_hashes_testing,
)
ByzantiumVMForTesting = ByzantiumVM.configure(
    __name__='ByzantiumVMForTesting',
    _state_class=ByzantiumStateForTesting,
    get_prev_hashes=get_prev_hashes_testing,
)


@pytest.fixture
def fixture_vm_class(fixture_data):
    _, _, fork_name, _ = fixture_data
    if fork_name == ForkName.Frontier:
        return FrontierVMForTesting
    elif fork_name == ForkName.Homestead:
        return HomesteadVMForTesting
    elif fork_name == ForkName.EIP150:
        return TangerineWhistleVMForTesting
    elif fork_name == ForkName.EIP158:
        return SpuriousDragonVMForTesting
    elif fork_name == ForkName.Byzantium:
        return ByzantiumVMForTesting
    elif fork_name == ForkName.Constantinople:
        pytest.skip("Constantinople VM has not been implemented")
    elif fork_name == ForkName.Metropolis:
        pytest.skip("Metropolis VM has not been implemented")
    else:
        raise ValueError("Unknown Fork Name: {0}".format(fork_name))


def test_state_fixtures(fixture, fixture_vm_class):
    header = BlockHeader(
        coinbase=fixture['env']['currentCoinbase'],
        difficulty=fixture['env']['currentDifficulty'],
        block_number=fixture['env']['currentNumber'],
        gas_limit=fixture['env']['currentGasLimit'],
        timestamp=fixture['env']['currentTimestamp'],
        parent_hash=fixture['env']['previousHash'],
    )

    chaindb = ChainDB(get_db_backend())
    vm = fixture_vm_class(header=header, chaindb=chaindb)

    state = vm.state
    apply_state_dict(state.account_db, fixture['pre'])
    state.account_db.persist()

    # Update state_root manually
    vm.block = vm.block.copy(header=vm.block.header.copy(state_root=state.state_root))
    if 'secretKey' in fixture['transaction']:
        unsigned_transaction = vm.create_unsigned_transaction(
            nonce=fixture['transaction']['nonce'],
            gas_price=fixture['transaction']['gasPrice'],
            gas=fixture['transaction']['gasLimit'],
            to=fixture['transaction']['to'],
            value=fixture['transaction']['value'],
            data=fixture['transaction']['data'],
        )
        private_key = keys.PrivateKey(fixture['transaction']['secretKey'])
        transaction = unsigned_transaction.as_signed_transaction(private_key=private_key)
    elif 'vrs' in fixture['transaction']:
        v, r, s = (
            fixture['transaction']['v'],
            fixture['transaction']['r'],
            fixture['transaction']['s'],
        )
        transaction = vm.create_transaction(
            nonce=fixture['transaction']['nonce'],
            gas_price=fixture['transaction']['gasPrice'],
            gas=fixture['transaction']['gasLimit'],
            to=fixture['transaction']['to'],
            value=fixture['transaction']['value'],
            data=fixture['transaction']['data'],
            v=v,
            r=r,
            s=s,
        )

    try:
        header, receipt, computation = vm.apply_transaction(vm.block.header, transaction)
        transactions = vm.block.transactions + (transaction, )
        receipts = vm.block.get_receipts(chaindb) + (receipt, )
        block = vm.set_block_transactions(vm.block, header, transactions, receipts)
    except ValidationError as err:
        block = vm.block
        transaction_error = err
        logger.warn("Got transaction error", exc_info=True)
    else:
        transaction_error = False

    if not transaction_error:
        log_entries = computation.get_log_entries()
        actual_logs_hash = hash_log_entries(log_entries)
        if 'logs' in fixture['post']:
            expected_logs_hash = fixture['post']['logs']
            assert expected_logs_hash == actual_logs_hash
        elif log_entries:
            raise AssertionError("Got log {0} entries. hash:{1}".format(
                len(log_entries),
                actual_logs_hash,
            ))

        if 'out' in fixture:
            expected_output = fixture['out']
            if isinstance(expected_output, int):
                assert len(computation.output) == expected_output
            else:
                assert computation.output == expected_output

    assert block.header.state_root == fixture['post']['hash']
