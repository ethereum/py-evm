import pytest

import fnmatch
import json
import os

from trie.db.memory import (
    MemoryDB,
)

from eth_utils import (
    is_0x_prefixed,
    to_canonical_address,
    decode_hex,
    pad_left,
    keccak,
)

from evm.constants import (
    ZERO_ADDRESS,
)
from evm.exceptions import (
    InvalidTransaction,
)
from evm.vm.flavors import (
    FrontierEVM
)
from evm.rlp.headers import (
    BlockHeader,
)
from evm.rlp.blocks import (
    Block,
)
from evm.rlp.transactions import (
    UnsignedTransaction,
    sign_transaction,
)

from evm.utils.numeric import (
    int_to_big_endian,
    big_endian_to_int,
)
from evm.utils.padding import (
    pad32,
)


def to_int(value):
    if is_0x_prefixed(value):
        if len(value) == 2:
            return 0
        else:
            return int(value, 16)
    else:
        return int(value)


def normalize_statetest_fixture(fixture):
    normalized_fixture = {
        'env': {
            'currentCoinbase': decode_hex(fixture['env']['currentCoinbase']),
            'currentDifficulty': to_int(fixture['env']['currentDifficulty']),
            'currentNumber': to_int(fixture['env']['currentNumber']),
            'currentGasLimit': to_int(fixture['env']['currentGasLimit']),
            'currentTimestamp': to_int(fixture['env']['currentTimestamp']),
            'previousHash': decode_hex(fixture['env']['previousHash']),
        },
        'transaction': {
            'data': decode_hex(fixture['transaction']['data']),
            'gasLimit': to_int(fixture['transaction']['gasLimit']),
            'gasPrice': to_int(fixture['transaction']['gasPrice']),
            'nonce': to_int(fixture['transaction']['nonce']),
            'secretKey': decode_hex(fixture['transaction']['secretKey']),
            'to': (
                to_canonical_address(fixture['transaction']['to'])
                if fixture['transaction']['to']
                else ZERO_ADDRESS
            ),
            'value': to_int(fixture['transaction']['value']),
        },
        'pre': {
            to_canonical_address(address): {
                'balance': to_int(state['balance']),
                'code': decode_hex(state['code']),
                'nonce': to_int(state['nonce']),
                'storage': {
                    to_int(slot): big_endian_to_int(decode_hex(value))
                    for slot, value in state['storage'].items()
                },
            } for address, state in fixture['pre'].items()
        },
        'postStateRoot': decode_hex(fixture['postStateRoot']),
    }

    if 'post' in fixture:
        normalized_fixture['post'] = {
            to_canonical_address(address): {
                'balance': to_int(state['balance']),
                'code': decode_hex(state['code']),
                'nonce': to_int(state['nonce']),
                'storage': {
                    to_int(slot): big_endian_to_int(decode_hex(value))
                    for slot, value in state['storage'].items()
                },
            } for address, state in fixture['post'].items()
        }

    if 'out' in fixture:
        if fixture['out'].startswith('#'):
            normalized_fixture['out'] = int(fixture['out'][1:])
        else:
            normalized_fixture['out'] = decode_hex(fixture['out'])

    if 'logs' in fixture:
        normalized_fixture['logs'] = [
            {
                'address': to_canonical_address(log_entry['address']),
                'topics': [decode_hex(topic) for topic in log_entry['topics']],
                'data': decode_hex(log_entry['data']),
                # 'bloom': decode_hex(log_entry['bloom']),  #TODO
            } for log_entry in fixture['logs']
        ]

    return normalized_fixture


ROOT_PROJECT_DIR = os.path.dirname(os.path.dirname(__file__))


def recursive_find_files(base_dir, pattern):
    for dirpath, _, filenames in os.walk(base_dir):
        for filename in filenames:
            if fnmatch.fnmatch(filename, pattern):
                yield os.path.join(dirpath, filename)


BASE_FIXTURE_PATH = os.path.join(ROOT_PROJECT_DIR, 'fixtures', 'StateTests')


#FIXTURES_PATHS = tuple(recursive_find_files(BASE_FIXTURE_PATH, "*.json"))
FIXTURES_PATHS = (
    os.path.join(BASE_FIXTURE_PATH, "stBlockHashTest.json"),
    os.path.join(BASE_FIXTURE_PATH, "stCallCodes.json"),
    os.path.join(BASE_FIXTURE_PATH, "stCallCreateCallCodeTest.json"),
    os.path.join(BASE_FIXTURE_PATH, "stExample.json"),
    os.path.join(BASE_FIXTURE_PATH, "stInitCodeTest.json"),
    os.path.join(BASE_FIXTURE_PATH, "stLogTests.json"),
    #os.path.join(BASE_FIXTURE_PATH, "stMemoryStressTest.json"),  # slow
    os.path.join(BASE_FIXTURE_PATH, "stMemoryTest.json"),
    os.path.join(BASE_FIXTURE_PATH, "stPreCompiledContracts.json"),
    #os.path.join(BASE_FIXTURE_PATH, "stQuadraticComplexityTest.json"),  # slow
    os.path.join(BASE_FIXTURE_PATH, "stRecursiveCreate.json"),
    os.path.join(BASE_FIXTURE_PATH, "stRefundTest.json"),
    os.path.join(BASE_FIXTURE_PATH, "stSolidityTest.json"),
    os.path.join(BASE_FIXTURE_PATH, "stSpecialTest.json"),
    os.path.join(BASE_FIXTURE_PATH, "stSystemOperationsTest.json"),
    os.path.join(BASE_FIXTURE_PATH, "stTransactionTest.json"),
    os.path.join(BASE_FIXTURE_PATH, "stTransitionTest.json"),
    os.path.join(BASE_FIXTURE_PATH, "stWalletTest.json"),
)


RAW_FIXTURES = tuple(
    (
        os.path.basename(fixture_path),
        json.load(open(fixture_path)),
    ) for fixture_path in FIXTURES_PATHS
)


SUCCESS_FIXTURES = tuple(
    (
        "{0}:{1}".format(fixture_filename, key),
        normalize_statetest_fixture(fixtures[key]),
    )
    for fixture_filename, fixtures in RAW_FIXTURES
    for key in sorted(fixtures.keys())
    if 'post' in fixtures[key]
)


class EVMForTesting(FrontierEVM):
    #
    # Storage Overrides
    #
    def get_block_hash(self, block_number):
        if block_number >= self.block.header.block_number:
            return b''
        elif block_number < 0:
            return b''
        elif block_number < self.block.header.block_number - 256:
            return b''
        else:
            return keccak("{0}".format(block_number))


def setup_storage(account_fixtures, storage):
    for account, account_data in account_fixtures.items():
        for slot, value in account_data['storage'].items():
            storage.set_storage(account, slot, value)

        nonce = account_data['nonce']
        code = account_data['code']
        balance = account_data['balance']

        storage.set_nonce(account, nonce)
        storage.set_code(account, code)
        storage.set_balance(account, balance)
    return storage


@pytest.mark.parametrize(
    'fixture_name,fixture', SUCCESS_FIXTURES,
)
def test_vm_success_using_fixture(fixture_name, fixture):
    header = BlockHeader(
        coinbase=fixture['env']['currentCoinbase'],
        difficulty=fixture['env']['currentDifficulty'],
        block_number=fixture['env']['currentNumber'],
        gas_limit=fixture['env']['currentGasLimit'],
        timestamp=fixture['env']['currentTimestamp'],
        parent_hash=fixture['env']['previousHash'],
    )
    db = MemoryDB()
    block = Block(header=header, db=db)
    evm = EVMForTesting(
        db=db,
        block=block,
    )

    setup_storage(fixture['pre'], block.state_db)

    unsigned_transaction = UnsignedTransaction(
        nonce=fixture['transaction']['nonce'],
        gas_price=fixture['transaction']['gasPrice'],
        gas=fixture['transaction']['gasLimit'],
        to=fixture['transaction']['to'],
        value=fixture['transaction']['value'],
        data=fixture['transaction']['data'],
    )
    transaction = sign_transaction(unsigned_transaction, fixture['transaction']['secretKey'])

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

    for account, account_data in sorted(fixture['post'].items()):
        for slot, expected_storage_value in sorted(account_data['storage'].items()):
            actual_storage_value = evm.block.state_db.get_storage(account, slot)

            assert actual_storage_value == expected_storage_value

        expected_nonce = account_data['nonce']
        expected_code = account_data['code']
        expected_balance = account_data['balance']

        actual_nonce = evm.block.state_db.get_nonce(account)
        actual_code = evm.block.state_db.get_code(account)
        actual_balance = evm.block.state_db.get_balance(account)
        balance_delta = expected_balance - actual_balance

        assert actual_nonce == expected_nonce
        assert actual_code == expected_code
        assert balance_delta == 0, "Expected: {0} - Actual: {1} | Delta: {2}".format(expected_balance, actual_balance, balance_delta)

    assert evm.block.state_db.state.root_hash == fixture['postStateRoot']
