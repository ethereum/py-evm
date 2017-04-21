
import pytest

import json
import os

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
    genesis_header = BlockHeader(
        parent_hash=fixture['genesisBlockHeader']['parentHash'],
        uncles_hash=fixture['genesisBlockHeader']['uncleHash'],
        coinbase=fixture['genesisBlockHeader']['coinbase'],
        state_root=fixture['genesisBlockHeader']['stateRoot'],
        transaction_root=fixture['genesisBlockHeader']['transactionsTrie'],
        receipts_root=fixture['genesisBlockHeader']['receiptTrie'],
        bloom=fixture['genesisBlockHeader']['bloom'],
        difficulty=fixture['genesisBlockHeader']['difficulty'],
        block_number=fixture['genesisBlockHeader']['number'],
        gas_limit=fixture['genesisBlockHeader']['gasLimit'],
        gas_used=fixture['genesisBlockHeader']['gasUsed'],
        timestamp=fixture['genesisBlockHeader']['timestamp'],
        extra_data=fixture['genesisBlockHeader']['extraData'],
        mix_hash=fixture['genesisBlockHeader']['mixHash'],
        nonce=fixture['genesisBlockHeader']['nonce'],
    )
    db = MemoryDB()
    meta_evm = MainnetEVM(db=db, header=genesis_header)

    # 1 - seal the genesis block
    # 2 - initialize a new header and open block
    # 3 - apply the transactions in the block.
    # 4 - profit!!

    for block in fixture['blocks']:
        evm = meta_evm.get_evm()
        assert not block

    block = evm.block
    assert False
