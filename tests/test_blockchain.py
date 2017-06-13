import pytest

import json
import os

import rlp

from trie.db.memory import (
    MemoryDB,
)

from eth_utils import (
    keccak,
)

from evm.exceptions import (
    InvalidTransaction,
)
from evm.vm.evm import (
    MetaEVM,
)
from evm.vm.flavors import (
    MainnetEVM,
)
from evm.vm.flavors.mainnet import (
    FRONTIER_BLOCK_RANGE,
    HOMESTEAD_BLOCK_RANGE,
)
from evm.rlp.headers import (
    BlockHeader,
)

from evm.utils.fixture_tests import (
    recursive_find_files,
    normalize_blockchain_fixtures,
    setup_state_db,
)


ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(__file__))


BASE_FIXTURE_PATH = os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'BlockchainTests')


#FIXTURES_PATHS = tuple(recursive_find_files(BASE_FIXTURE_PATH, "*.json"))
#FIXTURES_PATHS = tuple(recursive_find_files(HOMESTEAD_FIXTURE_PATH, "*.json"))
FIXTURES_PATHS = (
    os.path.join(BASE_FIXTURE_PATH, "bcValidBlockTest.json"),
)


RAW_FIXTURES = tuple(
    (
        os.path.relpath(fixture_path, BASE_FIXTURE_PATH),
        json.load(open(fixture_path)),
    )
    for fixture_path in FIXTURES_PATHS
    if (
        "Stress" not in fixture_path and
        "Complexity" not in fixture_path and
        "EIP150" not in fixture_path and
        "EIP158" not in fixture_path
    )
)


FIXTURES = tuple(
    (
        "{0}:{1}".format(fixture_filename, key),
        normalize_blockchain_fixtures(fixtures[key]),
    )
    for fixture_filename, fixtures in RAW_FIXTURES
    for key in sorted(fixtures.keys())
)


@pytest.mark.parametrize(
    'fixture_name,fixture', FIXTURES,
)
def test_blockchain_fixtures(fixture_name, fixture):
    genesis_header_params = {
        'parent_hash': fixture['genesisBlockHeader']['parentHash'],
        'uncles_hash': fixture['genesisBlockHeader']['uncleHash'],
        'coinbase': fixture['genesisBlockHeader']['coinbase'],
        'state_root': fixture['genesisBlockHeader']['stateRoot'],
        'transaction_root': fixture['genesisBlockHeader']['transactionsTrie'],
        'receipts_root': fixture['genesisBlockHeader']['receiptTrie'],
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

    # TODO: find out if this is supposed to pass?
    # if 'genesisRLP' in fixture:
    #     assert rlp.encode(genesis_header) == fixture['genesisRLP']

    db = MemoryDB()
    meta_evm = MainnetEVM.from_genesis(
        db=db,
        genesis_header_params=genesis_header_params,
        genesis_state=fixture['pre'],
    )

    assert meta_evm.header.parent_hash == fixture['genesisBlockHeader']['parentHash']
    assert meta_evm.header.uncles_hash == fixture['genesisBlockHeader']['uncleHash']
    assert meta_evm.header.coinbase == fixture['genesisBlockHeader']['coinbase']
    assert meta_evm.header.state_root == fixture['genesisBlockHeader']['stateRoot']
    assert meta_evm.header.transaction_root == fixture['genesisBlockHeader']['transactionsTrie']
    assert meta_evm.header.receipts_root == fixture['genesisBlockHeader']['receiptTrie']
    assert meta_evm.header.bloom == fixture['genesisBlockHeader']['bloom']
    assert meta_evm.header.difficulty == fixture['genesisBlockHeader']['difficulty']
    assert meta_evm.header.block_number == fixture['genesisBlockHeader']['number']
    assert meta_evm.header.gas_limit == fixture['genesisBlockHeader']['gasLimit']
    assert meta_evm.header.gas_used == fixture['genesisBlockHeader']['gasUsed']
    assert meta_evm.header.timestamp == fixture['genesisBlockHeader']['timestamp']
    assert meta_evm.header.extra_data == fixture['genesisBlockHeader']['extraData']
    assert meta_evm.header.mix_hash == fixture['genesisBlockHeader']['mixHash']
    assert meta_evm.header.nonce == fixture['genesisBlockHeader']['nonce']

    # 1 - seal the genesis block
    # 2 - initialize a new header and open block
    # 3 - apply the transactions in the block.
    # 4 - profit!!

    for block in fixture['blocks']:
        evm = meta_evm.get_evm()
        expected_header = BlockHeader(
            parent_hash=block['blockHeader']['parentHash'],
            uncles_hash=block['blockHeader']['uncleHash'],
            coinbase=block['blockHeader']['coinbase'],
            state_root=block['blockHeader']['stateRoot'],
            transaction_root=block['blockHeader']['transactionsTrie'],
            receipts_root=block['blockHeader']['receiptTrie'],
            bloom=block['blockHeader']['bloom'],
            difficulty=block['blockHeader']['difficulty'],
            block_number=block['blockHeader']['number'],
            gas_limit=block['blockHeader']['gasLimit'],
            gas_used=block['blockHeader']['gasUsed'],
            timestamp=block['blockHeader']['timestamp'],
            extra_data=block['blockHeader']['extraData'],
            mix_hash=block['blockHeader']['mixHash'],
            nonce=block['blockHeader']['nonce'],
        )

        if 'rlp' in block:
            pass
            #assert rlp.encode(expected_header) == block['rlp']

        for transaction in block['transactions']:
            txn_kwargs = {
                'data': transaction['data'],
                'gas': transaction['gasLimit'],
                'gas_price': transaction['gasPrice'],
                'nonce': transaction['nonce'],
                'to': transaction['to'],
                'value': transaction['value'],
                'r': transaction['r'],
                's': transaction['s'],
                'v': transaction['v'],
            }
            meta_evm.apply_transaction(txn_kwargs=txn_kwargs)

        actual_header = meta_evm.finalize_block(
            coinbase=block['blockHeader']['coinbase'],
            mix_hash=block['blockHeader']['mixHash'],
        )
        assert actual_header == expected_header
        assert False

    block = evm.block
    assert False
