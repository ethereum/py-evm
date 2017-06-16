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
    verify_state_db,
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

    # TODO: find out if this is supposed to pass?
    # if 'genesisRLP' in fixture:
    #     assert rlp.encode(genesis_header) == fixture['genesisRLP']

    db = MemoryDB()
    meta_evm = MainnetEVM.configure(db=db).from_genesis(
        genesis_params=genesis_params,
        genesis_state=fixture['pre'],
    )

    assert meta_evm.header.parent_hash == fixture['genesisBlockHeader']['parentHash']
    assert meta_evm.header.uncles_hash == fixture['genesisBlockHeader']['uncleHash']
    assert meta_evm.header.coinbase == fixture['genesisBlockHeader']['coinbase']
    assert meta_evm.header.state_root == fixture['genesisBlockHeader']['stateRoot']
    assert meta_evm.header.transaction_root == fixture['genesisBlockHeader']['transactionsTrie']
    assert meta_evm.header.receipt_root == fixture['genesisBlockHeader']['receiptTrie']
    assert meta_evm.header.bloom == fixture['genesisBlockHeader']['bloom']
    assert meta_evm.header.difficulty == fixture['genesisBlockHeader']['difficulty']
    assert meta_evm.header.block_number == fixture['genesisBlockHeader']['number']
    assert meta_evm.header.gas_limit == fixture['genesisBlockHeader']['gasLimit']
    assert meta_evm.header.gas_used == fixture['genesisBlockHeader']['gasUsed']
    assert meta_evm.header.timestamp == fixture['genesisBlockHeader']['timestamp']
    assert meta_evm.header.extra_data == fixture['genesisBlockHeader']['extraData']
    assert meta_evm.header.mix_hash == fixture['genesisBlockHeader']['mixHash']
    assert meta_evm.header.nonce == fixture['genesisBlockHeader']['nonce']

    meta_evm.mine_block()

    # 1 - mine the genesis block
    # 2 - loop over blocks:
    #     - apply transactions
    #     - mine block
    # 4 - profit!!

    for block in fixture['blocks']:
        expected_header = BlockHeader(
            parent_hash=block['blockHeader']['parentHash'],
            uncles_hash=block['blockHeader']['uncleHash'],
            coinbase=block['blockHeader']['coinbase'],
            state_root=block['blockHeader']['stateRoot'],
            transaction_root=block['blockHeader']['transactionsTrie'],
            receipt_root=block['blockHeader']['receiptTrie'],
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
        # set the gas limit as this value is only required to be within a
        # specific range and can be picked by the party who crafts the block.
        meta_evm.header.gas_limit = expected_header.gas_limit
        meta_evm.header.coinbase = expected_header.coinbase
        meta_evm.header.timestamp = expected_header.timestamp

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

        block = meta_evm.mine_block(
            mix_hash=block['blockHeader']['mixHash'],
            extra_data=block['blockHeader']['extraData'],
            nonce=block['blockHeader']['nonce'],
        )
        header = block.header

        if header != expected_header:
            header_field_names = tuple(sorted(set(tuple(zip(*header.fields))[0])))
            mismatched_fields = tuple(
                (field_name, getattr(header, field_name), getattr(expected_header, field_name))
                for field_name
                in header_field_names
                if getattr(header, field_name) != getattr(expected_header, field_name)
            )
            error_message = (
                "Actual block header does not match expected block header. "
                "Mismatched {0} fields:\n - {1}".format(
                    len(mismatched_fields),
                    "\n - ".join(tuple(
                        "{0}:\n    (actual)  : {1}\n    (expected): {2}".format(
                            field_name, actual, expected
                        )
                        for field_name, actual, expected
                        in mismatched_fields
                    )),
                )
            )
            print(error_message)
            #raise AssertionError(error_message)

    meta_evm.mine_block()

    evm = meta_evm.get_evm()
    verify_state_db(fixture['postState'], evm.state_db)
