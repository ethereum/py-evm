import pytest

import os

from trie.db.memory import (
    MemoryDB,
)

from eth_utils import (
    keccak,
)

from evm import (
    EVM,
)
from evm.exceptions import (
    InvalidTransaction,
)
from evm.vm.flavors import (
    FrontierVM,
    HomesteadVM,
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


def state_fixture_skip_fn(fixture_path, fixture_name, fixture):
    return (
        "Stress" in fixture_path or
        "Complexity" in fixture_path or
        "EIP150" in fixture_path or  # TODO: enable
        "EIP158" in fixture_path  # TODO: enable
    )


# These tests all take more than 1 second to run.
SLOW_FIXTURE_NAMES = {
    'Homestead/stCallCreateCallCodeTest.json:Call1024OOG',
    'Homestead/stCallCreateCallCodeTest.json:CallRecursiveBombPreCall',
    'Homestead/stCallCreateCallCodeTest.json:Callcode1024OOG',
    'Homestead/stCallCreateCallCodeTest.json:callcodeWithHighValueAndGasOOG',
    'Homestead/stCallCreateCallCodeTest.json:createInitFailStackSizeLargerThan1024',
    'Homestead/stDelegatecallTest.json:Call1024OOG',
    'Homestead/stDelegatecallTest.json:CallRecursiveBombPreCall',
    'Homestead/stDelegatecallTest.json:Delegatecall1024OOG',
    'Homestead/stMemoryTest.json:stackLimitGas_1023',
    'Homestead/stRecursiveCreate.json:recursiveCreateReturnValue',
    'Homestead/stSpecialTest.json:JUMPDEST_Attack',
    'Homestead/stSpecialTest.json:JUMPDEST_AttackwithJump',
    'Homestead/stSystemOperationsTest.json:ABAcalls1',
    'Homestead/stSystemOperationsTest.json:ABAcalls2',
    'Homestead/stSystemOperationsTest.json:ABAcalls3',
    'Homestead/stSystemOperationsTest.json:CallRecursiveBomb0',
    'Homestead/stSystemOperationsTest.json:CallRecursiveBomb0_OOG_atMaxCallDepth',
    'Homestead/stSystemOperationsTest.json:CallRecursiveBomb1',
    'Homestead/stSystemOperationsTest.json:CallRecursiveBomb2',
    'Homestead/stSystemOperationsTest.json:CallRecursiveBomb3',
    'Homestead/stSystemOperationsTest.json:CallRecursiveBombLog',
    'Homestead/stSystemOperationsTest.json:CallRecursiveBombLog2',
    'Homestead/stWalletTest.json:walletAddOwnerRemovePendingTransaction',
    'stBlockHashTest.json:blockhashDOS-sec71',
    'stCallCreateCallCodeTest.json:Call1024OOG',
    'stCallCreateCallCodeTest.json:CallRecursiveBombPreCall',
    'stCallCreateCallCodeTest.json:Callcode1024OOG',
    'stRecursiveCreate.json:recursiveCreateReturnValue',
    'stSolidityTest.json:CallInfiniteLoop',
    'stSpecialTest.json:JUMPDEST_Attack',
    'stSpecialTest.json:JUMPDEST_AttackwithJump',
    'stSpecialTest.json:block504980',
    'stSystemOperationsTest.json:ABAcalls1',
    'stSystemOperationsTest.json:ABAcalls2',
    'stSystemOperationsTest.json:ABAcalls3',
    'stSystemOperationsTest.json:CallRecursiveBomb0',
    'stSystemOperationsTest.json:CallRecursiveBomb0_OOG_atMaxCallDepth',
    'stSystemOperationsTest.json:CallRecursiveBomb1',
    'stSystemOperationsTest.json:CallRecursiveBomb2',
    'stSystemOperationsTest.json:CallRecursiveBomb3',
    'stSystemOperationsTest.json:CallRecursiveBombLog',
    'stSystemOperationsTest.json:CallRecursiveBombLog2',
}


def state_fixture_mark_fn(fixture_name):
    if fixture_name in SLOW_FIXTURE_NAMES:
        return pytest.mark.state_slow
    else:
        return None


FIXTURES = find_fixtures(
    BASE_FIXTURE_PATH,
    normalize_statetest_fixture,
    skip_fn=state_fixture_skip_fn,
    mark_fn=state_fixture_mark_fn,
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


FrontierVMForTesting = FrontierVM.configure(
    name='FrontierVMForTesting',
    get_block_hash=get_block_hash_for_testing,
)
HomesteadVMForTesting = HomesteadVM.configure(
    name='HomesteadVMForTesting',
    get_block_hash=get_block_hash_for_testing,
)


EVMForTesting = EVM.configure(
    name='EVMForTesting',
    vm_block_ranges=(
        (FRONTIER_BLOCK_RANGE, FrontierVMForTesting),
        (HOMESTEAD_BLOCK_RANGE, HomesteadVMForTesting),
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
    evm = EVMForTesting.configure(db=db)(header=header)

    state_db = setup_state_db(fixture['pre'], evm.get_state_db())
    evm.header.state_root = state_db.root_hash

    unsigned_transaction = evm.create_unsigned_transaction(
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

    verify_state_db(fixture['post'], evm.get_state_db())
