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
    InvalidBlock,
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

    genesis_block = meta_evm.get_block_by_number(0)
    genesis_header = genesis_block.header

    assert genesis_header.parent_hash == fixture['genesisBlockHeader']['parentHash']
    assert genesis_header.uncles_hash == fixture['genesisBlockHeader']['uncleHash']
    assert genesis_header.coinbase == fixture['genesisBlockHeader']['coinbase']
    assert genesis_header.state_root == fixture['genesisBlockHeader']['stateRoot']
    assert genesis_header.transaction_root == fixture['genesisBlockHeader']['transactionsTrie']
    assert genesis_header.receipt_root == fixture['genesisBlockHeader']['receiptTrie']
    assert genesis_header.bloom == fixture['genesisBlockHeader']['bloom']
    assert genesis_header.difficulty == fixture['genesisBlockHeader']['difficulty']
    assert genesis_header.block_number == fixture['genesisBlockHeader']['number']
    assert genesis_header.gas_limit == fixture['genesisBlockHeader']['gasLimit']
    assert genesis_header.gas_used == fixture['genesisBlockHeader']['gasUsed']
    assert genesis_header.timestamp == fixture['genesisBlockHeader']['timestamp']
    assert genesis_header.extra_data == fixture['genesisBlockHeader']['extraData']
    assert genesis_header.mix_hash == fixture['genesisBlockHeader']['mixHash']
    assert genesis_header.nonce == fixture['genesisBlockHeader']['nonce']

    # 1 - mine the genesis block
    # 2 - loop over blocks:
    #     - apply transactions
    #     - mine block
    # 4 - profit!!

    for block_data in fixture['blocks']:
        should_be_good_block = any((
            'blockHeader' in block_data,
            'transactions' in block_data,
            'uncleHeaders' in block_data,
        ))

        try:
            expected_block = rlp.decode(
                block_data['rlp'],
                sedes=meta_evm.get_evm().get_block_class(),
            )
        except Exception as arst:
            assert not should_be_good_block, "Block should be good"
            continue

        try:
            expected_block.validate()
        except InvalidBlock:
            assert not should_be_good_block, "Block should be good"
            continue

        expected_header = BlockHeader(
            parent_hash=block_data['blockHeader']['parentHash'],
            uncles_hash=block_data['blockHeader']['uncleHash'],
            coinbase=block_data['blockHeader']['coinbase'],
            state_root=block_data['blockHeader']['stateRoot'],
            transaction_root=block_data['blockHeader']['transactionsTrie'],
            receipt_root=block_data['blockHeader']['receiptTrie'],
            bloom=block_data['blockHeader']['bloom'],
            difficulty=block_data['blockHeader']['difficulty'],
            block_number=block_data['blockHeader']['number'],
            gas_limit=block_data['blockHeader']['gasLimit'],
            gas_used=block_data['blockHeader']['gasUsed'],
            timestamp=block_data['blockHeader']['timestamp'],
            extra_data=block_data['blockHeader']['extraData'],
            mix_hash=block_data['blockHeader']['mixHash'],
            nonce=block_data['blockHeader']['nonce'],
        )
        # set the gas limit as this value is only required to be within a
        # specific range and can be picked by the party who crafts the block.
        meta_evm.setup_header(
            extra_data=expected_block.header.extra_data,
            gas_limit=expected_block.header.gas_limit,
            coinbase=expected_block.header.coinbase,
            timestamp=expected_block.header.timestamp,
        )

        for transaction in block_data['transactions']:
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
            computation = meta_evm.apply_transaction(txn_kwargs=txn_kwargs)

        block = meta_evm.mine_block(
            mix_hash=expected_block.header.mix_hash,
            nonce=expected_block.header.nonce,
        )
        assert block == expected_block
        assert rlp.encode(block) == block_data['rlp']

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
            raise AssertionError(error_message)

        assert header == expected_header

    evm = meta_evm.get_evm()
    verify_state_db(fixture['postState'], evm.state_db)
