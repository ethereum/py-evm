import pytest

import os

import rlp

from evm.db import (
    get_db_backend,
)

from eth_utils import (
    keccak,
)

from evm import (
    constants,
    EVM,
)
from evm.exceptions import (
    ValidationError,
)
from evm.vm.flavors import (
    EIP150VM,
    FrontierVM,
    HomesteadVM,
    MainnetEVM,
)
from evm.rlp.headers import (
    BlockHeader,
)

from evm.utils.fixture_tests import (
    find_fixtures,
    normalize_blockchain_fixtures,
    setup_state_db,
    verify_state_db,
    assert_rlp_equal,
)


ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


BASE_FIXTURE_PATH = os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'BlockchainTests')


# A list of individual tests (fixture_path:fixture_name) that are disable
# because of any reasons.
DISABLED_INDIVIDUAL_TESTS = [
    "bcInvalidHeaderTest.json:ExtraData1024",
    "bcInvalidHeaderTest.json:DifferentExtraData1025",
    # This test alone takes more than 10 minutes to run, and that causes the
    # travis build to be terminated so it's disabled until we figure out how
    # to make it run faster.
    "Homestead/bcSuicideIssue.json:SuicideIssue",
    # These tests seem to have issues; they're disabled in geth as well.
    "TestNetwork/bcTheDaoTest.json:DaoTransactions",
    "TestNetwork/bcTheDaoTest.json:DaoTransactions_UncleExtradata",
]

def blockchain_fixture_skip_fn(fixture_path, fixture_name, fixture):
    # TODO: enable all tests
    return (
        ":".join([fixture_path, fixture_name]) in DISABLED_INDIVIDUAL_TESTS
    )


SLOW_FIXTURE_NAMES = {
    'bcForkStressTest.json:ForkStressTest',
    'bcWalletTest.json:walletReorganizeOwners',
    'Homestead/bcExploitTest.json:DelegateCallSpam',
    "Homestead/bcWalletTest.json:walletReorganizeOwners",
    "Homestead/bcShanghaiLove.json:Devcon2Attack",
    "Homestead/bcForkStressTest.json:ForkStressTest",
    "EIP150/bcWalletTest.json:walletReorganizeOwners",
    "EIP150/bcForkStressTest.json:ForkStressTest",
}


def blockchain_fixture_mark_fn(fixture_name):
    if fixture_name in SLOW_FIXTURE_NAMES:
        return pytest.mark.blockchain_slow
    else:
        return None


FIXTURES = find_fixtures(
    BASE_FIXTURE_PATH,
    normalize_blockchain_fixtures,
    skip_fn=blockchain_fixture_skip_fn,
    ignore_fn=blockchain_fixture_skip_fn,  # TODO: remove
    mark_fn=blockchain_fixture_mark_fn,
)


@pytest.mark.parametrize(
    'fixture_name,fixture', FIXTURES,
)
def test_blockchain_fixtures(fixture_name, fixture):
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

    db = get_db_backend()
    evm = MainnetEVM
    # TODO: It would be great if we can figure out an API for re-configuring
    # start block numbers that was more elegant.
    if fixture_name.startswith('Homestead'):
        evm = EVM.configure(
            'HomesteadEVM',
            vm_configuration=[(0, HomesteadVM)])
    elif fixture_name.startswith('EIP150'):
        evm = EVM.configure(
            'EIP150VM',
            vm_configuration=[(0, EIP150VM)])
    elif fixture_name.startswith('TestNetwork'):
        homestead_vm = HomesteadVM.configure(dao_fork_block_number=8)
        evm = EVM.configure(
            'TestNetworkEVM',
            vm_configuration=[
                (0, FrontierVM),
                (5, homestead_vm),
                (10, EIP150VM),
            ]
        )

    evm = evm.from_genesis(
        db,
        genesis_params=genesis_params,
        genesis_state=fixture['pre'],
    )

    genesis_block = evm.get_canonical_block_by_number(0)
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
        # evm's current one, so we use the block number specified in the
        # fixture to look up the correct block class.
        if should_be_good_block:
            block_number = block_data['blockHeader']['number']
            block_class = evm.get_vm_class_for_block_number(block_number).get_block_class()
        else:
            block_class = evm.get_vm().get_block_class()

        try:
            block = rlp.decode(block_data['rlp'], sedes=block_class, db=db)
        except (TypeError, rlp.DecodingError, rlp.DeserializationError) as err:
            assert not should_be_good_block, "Block should be good: {0}".format(err)
            continue

        try:
            mined_block = evm.import_block(block)
        except ValidationError as err:
            assert not should_be_good_block, "Block should be good: {0}".format(err)
            continue
        else:
            assert_rlp_equal(mined_block, block)
            assert should_be_good_block, "Block should have caused a validation error"

    assert evm.get_canonical_block_by_number(evm.get_block().number - 1).hash == fixture['lastblockhash']

    verify_state_db(fixture['postState'], evm.get_state_db())
