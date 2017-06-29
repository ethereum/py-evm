import pytest

import os

import rlp

from trie.db.memory import (
    MemoryDB,
)

from eth_utils import (
    keccak,
)

from evm.exceptions import (
    ValidationError,
)
from evm.vm.flavors import (
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


def blockchain_fixture_skip_fn(fixture_path, fixture_name, fixture):
    # TODO: enable all tests
    return (
        fixture_path.startswith('TestNetwork') or  # TODO: enable
        'Homestead' in fixture_path or  # TODO: enable
        'Homestead' in fixture_name or  # TODO: enable
        'EIP150' in fixture_path or  # TODO: enable
        'EIP150' in fixture_name or  # TODO: enable
        'EIP158' in fixture_path or  # TODO: enable
        'EIP158' in fixture_name   # TODO: enable
    )


SLOW_FIXTURE_NAMES = {
    'GeneralStateTests/stAttackTest/ContractCreationSpam.json:ContractCreationSpam_d0g0v0_Frontier',
    'GeneralStateTests/stBoundsTest/MLOAD_Bounds.json:MLOAD_Bounds_d0g0v0_Frontier',
    'GeneralStateTests/stMemoryStressTest/CALLCODE_Bounds3.json:CALLCODE_Bounds3_d0g0v0_Frontier',
    'GeneralStateTests/stMemoryStressTest/CALL_Bounds2.json:CALL_Bounds2_d0g0v0_Frontier',
    'GeneralStateTests/stMemoryStressTest/CALL_Bounds2a.json:CALL_Bounds2a_d0g0v0_Frontier',
    'GeneralStateTests/stCallCreateCallCodeTest/Call1024OOG.json:Call1024OOG_d0g0v0_Frontier',
    'GeneralStateTests/stCallCreateCallCodeTest/Callcode1024OOG.json:Callcode1024OOG_d0g0v0_Frontier',
    'GeneralStateTests/stCallCreateCallCodeTest/CallRecursiveBombPreCall.json:CallRecursiveBombPreCall_d0g0v0_Frontier',
    'bcForkStressTest.json:ForkStressTest',
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

    db = MemoryDB()
    evm = MainnetEVM.from_genesis(
        db,
        genesis_params=genesis_params,
        genesis_state=fixture['pre'],
    )

    genesis_block = evm.get_block_by_number(0)
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

    assert evm.get_block_by_number(evm.get_block().number - 1).hash == fixture['lastblockhash']

    verify_state_db(fixture['postState'], evm.get_state_db())
