import pytest

import os

import rlp

from evm.db import (
    get_db_backend,
)

from eth_utils import (
    keccak,
)

from evm import EVM
from evm.exceptions import (
    ValidationError,
)
from evm.vm.flavors import (
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
]

def blockchain_fixture_skip_fn(fixture_path, fixture_name, fixture):
    # TODO: enable all tests
    return (
        ":".join([fixture_path, fixture_name]) in DISABLED_INDIVIDUAL_TESTS or
        fixture_path.startswith('TestNetwork') or  # TODO: enable
        'EIP150' in fixture_path or  # TODO: enable
        'EIP150' in fixture_name or  # TODO: enable
        'EIP158' in fixture_path or  # TODO: enable
        'EIP158' in fixture_name   # TODO: enable
    )


SLOW_FIXTURE_NAMES = {
    'bcForkStressTest.json:ForkStressTest',
    'bcWalletTest.json:walletReorganizeOwners',
    'Homestead/bcExploitTest.json:DelegateCallSpam',
    "Homestead/bcWalletTest.json:walletReorganizeOwners",
    "Homestead/bcShanghaiLove.json:Devcon2Attack",
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

        try:
            block = rlp.decode(
                block_data['rlp'],
                sedes=evm.get_vm().get_block_class(),
                db=db,
            )
        except (TypeError, rlp.DecodingError, rlp.DeserializationError) as err:
            assert not should_be_good_block, "Block should be good: {0}".format(err)
            continue

        try:
            mined_block = evm.import_block(block)
            assert_rlp_equal(mined_block, block)
        except ValidationError as err:
            assert not should_be_good_block, "Block should be good: {0}".format(err)
            continue
        else:
            assert should_be_good_block, "Block should have caused a validation error"

    assert evm.get_canonical_block_by_number(evm.get_block().number - 1).hash == fixture['lastblockhash']

    verify_state_db(fixture['postState'], evm.get_state_db())
