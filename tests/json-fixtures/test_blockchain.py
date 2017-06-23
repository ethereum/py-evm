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
    InvalidBlock,
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
    find_fixtures,
    normalize_blockchain_fixtures,
    setup_state_db,
    verify_state_db,
)


ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


BASE_FIXTURE_PATH = os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'BlockchainTests')


def blockchain_fixture_skip_fn(fixture_path, fixture_name, fixture):
    # TODO: enable all tests
    return (
        'bcValidBlockTest' not in fixture_path or  # TODO: remove
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
    mark_fn=blockchain_fixture_mark_fn,
)


def diff_rlp_object(left, right):
    if type(left) is not type(right):
        raise AssertionError(
            "Type mismatch.  Got {0} and {1}".format(repr(type(left)), repr(type(right)))
        )

    rlp_type = type(left)

    rlp_field_names = tuple(sorted(set(tuple(zip(*rlp_type.fields))[0])))
    mismatched_fields = tuple(
        (field_name, getattr(left, field_name), getattr(right, field_name))
        for field_name
        in rlp_field_names
        if getattr(left, field_name) != getattr(right, field_name)
    )
    return mismatched_fields


def assert_rlp_equal(left, right):
    if left == right:
        return
    mismatched_fields = diff_rlp_object(left, right)
    error_message = (
        "RLP objects not equal for {0} fields:\n - {1}".format(
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
    evm = MainnetEVM.configure(db=db).from_genesis(
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
        should_be_good_block = any((
            'blockHeader' in block_data,
            'transactions' in block_data,
            'uncleHeaders' in block_data,
            'rlp_error' in block_data,
        ))

        if 'rlp_error' in block_data:
            assert not should_be_good_block
            continue

        try:
            expected_block = rlp.decode(
                block_data['rlp'],
                sedes=evm.get_vm().get_block_class(),
            )
        except :
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
        evm.configure_header(
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
            transaction = evm.create_transaction(**txn_kwargs)
            computation = evm.apply_transaction(transaction)

        block = evm.mine_block(
            mix_hash=expected_block.header.mix_hash,
            nonce=expected_block.header.nonce,
        )

        assert_rlp_equal(block.header, expected_header)
        assert_rlp_equal(block, expected_block)

        assert rlp.encode(block) == block_data['rlp']

    verify_state_db(fixture['postState'], evm.get_state_db())
