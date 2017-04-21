
import fnmatch
import os

from eth_utils import (
    is_0x_prefixed,
    to_canonical_address,
    decode_hex,
    remove_0x_prefix,
    pad_left,
)

from evm.constants import (
    CREATE_CONTRACT_ADDRESS,
)

from evm.utils.numeric import (
    big_endian_to_int,
)


#
# Filesystem fixture loading.
#
def recursive_find_files(base_dir, pattern):
    for dirpath, _, filenames in os.walk(base_dir):
        for filename in filenames:
            if fnmatch.fnmatch(filename, pattern):
                yield os.path.join(dirpath, filename)


#
# Fixture Normalization
#
def to_int(value):
    if is_0x_prefixed(value):
        if len(value) == 2:
            return 0
        else:
            return int(value, 16)
    else:
        return int(value)


def normalize_env(env):
    return {
        'currentCoinbase': decode_hex(env['currentCoinbase']),
        'currentDifficulty': to_int(env['currentDifficulty']),
        'currentNumber': to_int(env['currentNumber']),
        'currentGasLimit': to_int(env['currentGasLimit']),
        'currentTimestamp': to_int(env['currentTimestamp']),
        'previousHash': decode_hex(env.get('previousHash', '00' * 32)),
    }


def normalize_account_state(account_state):
    return {
        to_canonical_address(address): {
            'balance': to_int(state['balance']),
            'code': decode_hex(state['code']),
            'nonce': to_int(state['nonce']),
            'storage': {
                to_int(slot): big_endian_to_int(decode_hex(value))
                for slot, value in state['storage'].items()
            },
        } for address, state in account_state.items()
    }


def normalize_unsigned_transaction(transaction):
    return {
        'data': decode_hex(transaction['data']),
        'gasLimit': to_int(transaction['gasLimit']),
        'gasPrice': to_int(transaction['gasPrice']),
        'nonce': to_int(transaction['nonce']),
        'secretKey': decode_hex(transaction['secretKey']),
        'to': (
            to_canonical_address(transaction['to'])
            if transaction['to']
            else CREATE_CONTRACT_ADDRESS
        ),
        'value': to_int(transaction['value']),
    }


def normalize_logs(logs):
    return [
        {
            'address': to_canonical_address(log_entry['address']),
            'topics': [decode_hex(topic) for topic in log_entry['topics']],
            'data': decode_hex(log_entry['data']),
            'bloom': decode_hex(log_entry['bloom']),
        } for log_entry in logs
    ]


def normalize_statetest_fixture(fixture):
    normalized_fixture = {
        'env': normalize_env(fixture['env']),
        'transaction': normalize_unsigned_transaction(fixture['transaction']),
        'pre': normalize_account_state(fixture['pre']),
        'postStateRoot': decode_hex(fixture['postStateRoot']),
    }

    if 'post' in fixture:
        normalized_fixture['post'] = normalize_account_state(fixture['post'])

    if 'out' in fixture:
        if fixture['out'].startswith('#'):
            normalized_fixture['out'] = int(fixture['out'][1:])
        else:
            normalized_fixture['out'] = decode_hex(fixture['out'])

    if 'logs' in fixture:
        normalized_fixture['logs'] = normalize_logs(fixture['logs'])

    return normalized_fixture


def normalize_exec(exec_params):
    return {
        'origin': to_canonical_address(exec_params['origin']),
        'address': to_canonical_address(exec_params['address']),
        'caller': to_canonical_address(exec_params['caller']),
        'value': to_int(exec_params['value']),
        'data': decode_hex(exec_params['data']),
        'gas': to_int(exec_params['gas']),
        'gasPrice': to_int(exec_params['gasPrice']),
    }


def normalize_callcreates(callcreates):
    return [
        {
            'data': decode_hex(created_call['data']),
            'destination': (
                to_canonical_address(created_call['destination'])
                if created_call['destination']
                else CREATE_CONTRACT_ADDRESS
            ),
            'gasLimit': to_int(created_call['gasLimit']),
            'value': to_int(created_call['value']),
        } for created_call in callcreates
    ]


def normalize_vmtest_fixture(fixture):
    normalized_fixture = {
        'env': normalize_env(fixture['env']),
        'exec': normalize_exec(fixture['exec']),
        'pre': normalize_account_state(fixture['pre']),
    }

    if 'post' in fixture:
        normalized_fixture['post'] = normalize_account_state(fixture['post'])

    if 'callcreates' in fixture:
        normalized_fixture['callcreates'] = normalize_callcreates(fixture['callcreates'])

    if 'gas' in fixture:
        normalized_fixture['gas'] = to_int(fixture['gas'])

    if 'out' in fixture:
        normalized_fixture['out'] = decode_hex(fixture['out'])

    if 'logs' in fixture:
        normalized_fixture['logs'] = normalize_logs(fixture['logs'])

    return normalized_fixture


def robust_decode_hex(value):
    unprefixed_value = remove_0x_prefix(value)
    if len(unprefixed_value) % 2:
        return decode_hex(pad_left(unprefixed_value, len(unprefixed_value) + 1, b'0'))
    else:
        return decode_hex(unprefixed_value)


def normalize_signed_transaction(transaction):
    return {
        'data': robust_decode_hex(transaction['data']),
        'gasLimit': to_int(transaction['gasLimit']),
        'gasPrice': to_int(transaction['gasPrice']),
        'nonce': to_int(transaction['nonce']),
        'r': to_int(transaction['r']),
        's': to_int(transaction['s']),
        'v': to_int(transaction['v']),
        'to': decode_hex(transaction['to']),
        'value': to_int(transaction['value']),
    }


def normalize_transactiontest_fixture(fixture):
    normalized_fixture = {
        'blocknumber': to_int(fixture['blocknumber']),
        'rlp': decode_hex(fixture['rlp']),
    }

    if "sender" in fixture:
        # intentionally not normalized.
        normalized_fixture["transaction"] = fixture['transaction']
        # intentionally not normalized.
        normalized_fixture['sender'] = fixture['sender']
        normalized_fixture['hash'] = decode_hex(fixture['hash'])

    return normalized_fixture


#
# State Setup
#
def setup_state_db(desired_state, state_db):
    for account, account_data in desired_state.items():
        for slot, value in account_data['storage'].items():
            state_db.set_storage(account, slot, value)

        nonce = account_data['nonce']
        code = account_data['code']
        balance = account_data['balance']

        state_db.set_nonce(account, nonce)
        state_db.set_code(account, code)
        state_db.set_balance(account, balance)
    return state_db
