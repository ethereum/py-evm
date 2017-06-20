import pytest

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
    find_fixtures,
    normalize_statetest_fixture,
    setup_state_db,
    verify_state_db,
)


ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


BASE_FIXTURE_PATH = os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'StateTests')


def state_fixture_skip_fn(fixture_path):
    return (
        "Stress" in fixture_path or
        "Complexity" in fixture_path or
        "EIP150" in fixture_path or  # TODO: enable
        "EIP158" in fixture_path  # TODO: enable
    )


FIXTURES = find_fixtures(
    BASE_FIXTURE_PATH,
    normalize_statetest_fixture,
    state_fixture_skip_fn,
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


def test_found_state_fixtures():
    assert len(FIXTURES) != 0


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
