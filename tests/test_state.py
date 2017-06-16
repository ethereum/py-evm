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
    FrontierEVM,
    HomesteadEVM,
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
    normalize_statetest_fixture,
    setup_state_db,
    verify_state_db,
)


ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(__file__))


BASE_FIXTURE_PATH = os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'StateTests')


FIXTURES_PATHS = tuple(recursive_find_files(BASE_FIXTURE_PATH, "*.json"))


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
        normalize_statetest_fixture(fixtures[key]),
    )
    for fixture_filename, fixtures in RAW_FIXTURES
    for key in sorted(fixtures.keys())
    if 'post' in fixtures[key]
)


def get_block_hash_for_testing(self, block_number):
    if block_number >= self.block.header.block_number:
        return b''
    elif block_number < 0:
        return b''
    elif block_number < self.block.header.block_number - 256:
        return b''
    else:
        return keccak("{0}".format(block_number))


FrontierEVMForTesting = FrontierEVM.configure(
    name='FrontierEVMForTesting',
    get_block_hash=get_block_hash_for_testing,
)
HomesteadEVMForTesting = HomesteadEVM.configure(
    name='HomesteadEVMForTesting',
    get_block_hash=get_block_hash_for_testing,
)


EVMForTesting = MetaEVM.configure(
    name='EVMForTesting',
    evm_block_ranges=(
        (FRONTIER_BLOCK_RANGE, FrontierEVMForTesting),
        (HOMESTEAD_BLOCK_RANGE, HomesteadEVMForTesting),
    ),
)


@pytest.mark.parametrize(
    'fixture_name,fixture', FIXTURES,
)
def test_state_fixtures(fixture_name, fixture):
    header = BlockHeader(
        coinbase=fixture['env']['currentCoinbase'],
        difficulty=fixture['env']['currentDifficulty'],
        block_number=fixture['env']['currentNumber'],
        gas_limit=fixture['env']['currentGasLimit'],
        timestamp=fixture['env']['currentTimestamp'],
        parent_hash=fixture['env']['previousHash'],
    )
    db = MemoryDB()
    meta_evm = EVMForTesting.configure(db=db)(header=header)
    evm = meta_evm.get_evm()
    block = evm.block

    setup_state_db(fixture['pre'], evm.state_db)

    Transaction = evm.get_transaction_class()

    unsigned_transaction = Transaction.create_unsigned_transaction(
        nonce=fixture['transaction']['nonce'],
        gas_price=fixture['transaction']['gasPrice'],
        gas=fixture['transaction']['gasLimit'],
        to=fixture['transaction']['to'],
        value=fixture['transaction']['value'],
        data=fixture['transaction']['data'],
    )
    transaction = unsigned_transaction.as_signed_transaction(
        private_key=fixture['transaction']['secretKey']
    )

    try:
        computation = evm.apply_transaction(transaction)
    except InvalidTransaction:
        transaction_error = True
    else:
        transaction_error = False

    if not transaction_error:
        expected_logs = [
            {
                'address': log_entry[0],
                'topics': log_entry[1],
                'data': log_entry[2],
            }
            for log_entry in computation.get_log_entries()
        ]
        expected_logs == fixture['logs']

        expected_output = fixture['out']
        if isinstance(expected_output, int):
            assert len(computation.output) == expected_output
        else:
            assert computation.output == expected_output

    verify_state_db(fixture['post'], evm.state_db)
