import pytest

import os

import rlp

from evm.db import (
    get_db_backend,
)

from evm import (
    MainnetChain,
)
from evm.db.chain import BaseChainDB
from evm.exceptions import (
    ValidationError,
)
from evm.vm.forks import (
    EIP150VM,
    FrontierVM,
    HomesteadVM as BaseHomesteadVM,
    SpuriousDragonVM,
    ByzantiumVM,
)
from evm.rlp.headers import (
    BlockHeader,
)

from evm.utils.fixture_tests import (
    load_fixture,
    generate_fixture_tests,
    filter_fixtures,
    normalize_blockchain_fixtures,
    verify_state_db,
    assert_rlp_equal,
)


ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


BASE_FIXTURE_PATH = os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'BlockchainTests')


def blockchain_fixture_mark_fn(fixture_path, fixture_name):
    if fixture_path.startswith('GeneralStateTests'):
        return pytest.mark.skip(
            "General state tests are also exported as blockchain tests.  We "
            "skip them here so we don't run them twice"
        )
    elif fixture_path.startswith('bcExploitTest'):
        return pytest.mark.skip("Exploit tests are slow")
    elif fixture_path == 'bcWalletTest/walletReorganizeOwners.json':
        return pytest.mark.skip("Wallet owner reorganizatio tests are slow")


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
    return fixture


@pytest.fixture
def chain_vm_configuration(fixture_data, fixture):
    network = fixture['network']

    if network == 'Frontier':
        return (
            (0, FrontierVM),
        )
    elif network == 'Homestead':
        HomesteadVM = BaseHomesteadVM.configure(support_dao_fork=False)
        return (
            (0, HomesteadVM),
        )
    elif network == 'EIP150':
        return (
            (0, EIP150VM),
        )
    elif network == 'EIP158':
        return (
            (0, SpuriousDragonVM),
        )
    elif network == 'Byzantium':
        return (
            (0, ByzantiumVM),
        )
    elif network == 'Constantinople':
        pytest.skip('Constantinople VM rules not yet supported')
    elif network == 'FrontierToHomesteadAt5':
        HomesteadVM = BaseHomesteadVM.configure(support_dao_fork=False)
        return (
            (0, FrontierVM),
            (5, HomesteadVM),
        )
    elif network == 'HomesteadToEIP150At5':
        HomesteadVM = BaseHomesteadVM.configure(support_dao_fork=False)
        return (
            (0, HomesteadVM),
            (5, EIP150VM),
        )
    elif network == 'HomesteadToDaoAt5':
        HomesteadVM = BaseHomesteadVM.configure(
            support_dao_fork=True,
            dao_fork_block_number=5,
        )
        return (
            (0, HomesteadVM),
        )
    elif network == 'EIP158ToByzantiumAt5':
        return (
            (0, SpuriousDragonVM),
            (5, ByzantiumVM),
        )
    else:
        fixture_path, fixture_key = fixture_data
        raise AssertionError(
            "Test fixture did not match any configuration rules: {0}:{1}".format(
                fixture_path,
                fixture_key,
            )
        )


def test_blockchain_fixtures(fixture, chain_vm_configuration):
    genesis_params = {
        'parent_hash': fixture['genesisBlockHeader']['parentHash'],
        'uncles_hash': fixture['genesisBlockHeader']['uncleHash'],
        'coinbase': fixture['genesisBlockHeader']['coinbase'],
        'state_root': fixture['genesisBlockHeader']['stateRoot'],
        'transaction_root': fixture['genesisBlockHeader']['transactionsTrie'],
        'receipt_root': fixture['genesisBlockHeader']['receiptTrie'],
        'bloom': fixture['genesisBlockHeader']['bloom'],
        'difficulty': fixture['genesisBlockHeader']['difficulty'],
        'block_number': fixture['genesisBlockHeader']['number'],
        'gas_limit': fixture['genesisBlockHeader']['gasLimit'],
        'gas_used': fixture['genesisBlockHeader']['gasUsed'],
        'timestamp': fixture['genesisBlockHeader']['timestamp'],
        'extra_data': fixture['genesisBlockHeader']['extraData'],
        'mix_hash': fixture['genesisBlockHeader']['mixHash'],
        'nonce': fixture['genesisBlockHeader']['nonce'],
    }
    expected_genesis_header = BlockHeader(**genesis_params)

    # TODO: find out if this is supposed to pass?
    # if 'genesisRLP' in fixture:
    #     assert rlp.encode(genesis_header) == fixture['genesisRLP']
    db = BaseChainDB(get_db_backend())

    ChainForTesting = MainnetChain.configure(
        'ChainForTesting',
        vm_configuration=chain_vm_configuration,
    )

    chain = ChainForTesting.from_genesis(
        db,
        genesis_params=genesis_params,
        genesis_state=fixture['pre'],
    )

    genesis_block = chain.get_canonical_block_by_number(0)
    genesis_header = genesis_block.header

    assert_rlp_equal(genesis_header, expected_genesis_header)

    # 1 - mine the genesis block
    # 2 - loop over blocks:
    #     - apply transactions
    #     - mine block
    # 4 - profit!!

    for block_data in fixture['blocks']:
        should_be_good_block = 'blockHeader' in block_data

        if 'rlp_error' in block_data:
            assert not should_be_good_block
            continue

        # The block to import may be in a different block-class-range than the
        # chain's current one, so we use the block number specified in the
        # fixture to look up the correct block class.
        if should_be_good_block:
            block_number = block_data['blockHeader']['number']
            block_class = chain.get_vm_class_for_block_number(block_number).get_block_class()
        else:
            block_class = chain.get_vm().get_block_class()

        try:
            block = rlp.decode(block_data['rlp'], sedes=block_class, chaindb=chain.chaindb)
        except (TypeError, rlp.DecodingError, rlp.DeserializationError) as err:
            assert not should_be_good_block, "Block should be good: {0}".format(err)
            continue

        try:
            mined_block = chain.import_block(block)
        except ValidationError as err:
            assert not should_be_good_block, "Block should be good: {0}".format(err)
            continue
        else:
            assert_rlp_equal(mined_block, block)
            assert should_be_good_block, "Block should have caused a validation error"

    latest_block_hash = chain.get_canonical_block_by_number(chain.get_block().number - 1).hash
    assert latest_block_hash == fixture['lastblockhash']

    with chain.get_vm().state_db(read_only=True) as state_db:
        verify_state_db(fixture['postState'], state_db)
