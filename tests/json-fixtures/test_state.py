import os

import pytest

from eth_keys import keys

from evm.db import (
    get_db_backend,
)

from eth_utils import (
    keccak,
    to_tuple,
)

from evm.db.chain import BaseChainDB
from evm.exceptions import (
    ValidationError,
)
from evm.vm.forks import (
    EIP150VM,
    FrontierVM,
    HomesteadVM,
    SpuriousDragonVM,
    ByzantiumVM,
)
from evm.rlp.headers import (
    BlockHeader,
)
from evm.utils.fixture_tests import (
    filter_fixtures,
    generate_fixture_tests,
    hash_log_entries,
    load_fixture,
    normalize_statetest_fixture,
    setup_state_db,
)


ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


BASE_FIXTURE_PATH = os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'GeneralStateTests')


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


def mark_statetest_fixtures(fixture_path, fixture_key, fixture_fork, fixture_index):
    if fixture_path.startswith('stTransactionTest/zeroSigTransa'):
        return pytest.mark.skip("EIP-86 not supported.")
    elif fixture_path.startswith('stQuadraticComplexityTest'):
        return pytest.mark.skip("Quadratic complexity tests are SLOWWWWWW")


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
    if block_number >= self.block.header.block_number:
        return b''
    elif block_number < 0:
        return b''
    elif block_number < self.block.header.block_number - 256:
        return b''
    else:
        return keccak("{0}".format(block_number))


FrontierVMForTesting = FrontierVM.configure(
    name='FrontierVMForTesting',
    get_ancestor_hash=get_block_hash_for_testing,
)
HomesteadVMForTesting = HomesteadVM.configure(
    name='HomesteadVMForTesting',
    get_ancestor_hash=get_block_hash_for_testing,
)
EIP150VMForTesting = EIP150VM.configure(
    name='EIP150VMForTesting',
    get_ancestor_hash=get_block_hash_for_testing,
)
SpuriousDragonVMForTesting = SpuriousDragonVM.configure(
    name='SpuriousDragonVMForTesting',
    get_ancestor_hash=get_block_hash_for_testing,
)
ByzantiumVMForTesting = ByzantiumVM.configure(
    name='ByzantiumVMForTesting',
    get_ancestor_hash=get_block_hash_for_testing,
)


@pytest.fixture
def fixture_vm_class(fixture_data):
    _, _, fork_name, _ = fixture_data
    if fork_name == 'Frontier':
        return FrontierVMForTesting
    elif fork_name == 'Homestead':
        return HomesteadVMForTesting
    elif fork_name == 'EIP150':
        return EIP150VMForTesting
    elif fork_name == 'EIP158':
        return SpuriousDragonVMForTesting
    elif fork_name == 'Byzantium':
        return ByzantiumVMForTesting
    elif fork_name == 'Constantinople':
        pytest.skip("Constantinople VM has not been implemented")
    elif fork_name == 'Metropolis':
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
    chaindb = BaseChainDB(get_db_backend())
    vm = fixture_vm_class(header=header, chaindb=chaindb)

    with vm.state_db() as state_db:
        setup_state_db(fixture['pre'], state_db)

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
        computation = vm.apply_transaction(transaction)
    except ValidationError as err:
        transaction_error = err
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

    assert vm.block.header.state_root == fixture['post']['hash']
