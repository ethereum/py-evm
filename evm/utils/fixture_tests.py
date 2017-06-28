import binascii
import fnmatch
import json
import os

import pytest

from eth_utils import (
    is_0x_prefixed,
    to_canonical_address,
    to_normalized_address,
    decode_hex,
    remove_0x_prefix,
    pad_left,
    to_tuple,
)

from evm.constants import (
    CREATE_CONTRACT_ADDRESS,
)

from .numeric import (
    big_endian_to_int,
)
from .state import (
    diff_state_db,
)
from .rlp import (
    diff_rlp_object,
)


#
# Filesystem fixture loading.
#
@to_tuple
def _recursive_find_files(base_dir, pattern):
    for dirpath, _, filenames in os.walk(base_dir):
        for filename in filenames:
            if fnmatch.fnmatch(filename, pattern):
                yield os.path.join(dirpath, filename)


@to_tuple
def find_fixtures(fixtures_base_dir, normalize_fn, skip_fn=None, mark_fn=None, ignore_fn=None):
    """
    Helper function for JSON based fixture test suite.

    - `fixtures_base_dir`: the filesystem path under which JSON fixtures can be found.
    - `normalize_fn`: callback to normalize json fixture to internal format.
    - `skip_fn`: callback to skip any tests that should not be run.
    """
    all_fixture_paths = _recursive_find_files(fixtures_base_dir, "*.json")

    for fixture_path in sorted(all_fixture_paths):
        with open(fixture_path) as fixture_file:
            fixtures = json.load(fixture_file)

        for key in sorted(fixtures.keys()):
            fixture_relpath = os.path.relpath(fixture_path, fixtures_base_dir)

            fixture_name = "{0}:{1}".format(fixture_relpath, key)

            if ignore_fn:
                if ignore_fn(fixture_relpath, key, fixtures[key]):
                    continue

            normalized_fixture = normalize_fn(fixtures[key])

            if skip_fn:
                if skip_fn(fixture_relpath, key, fixtures[key]):
                    yield pytest.param(
                        fixture_name,
                        normalized_fixture,
                        marks=pytest.mark.skip(reason="Did not pass fixture skip fn"),
                    )
                    continue

            if mark_fn:
                mark = mark_fn(fixture_name)
                if mark:
                    yield pytest.param(
                        fixture_name,
                        normalized_fixture,
                        marks=mark,
                    )
                    continue

            yield fixture_name, normalized_fixture


#
# RLP Diffing
#


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
            'topics': [int(topic, 16) for topic in log_entry['topics']],
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
    normalized_fixture = {}

    if 'blocknumber' in fixture:
        normalized_fixture['blocknumber'] = to_int(fixture['blocknumber'])

    try:
        normalized_fixture['rlp'] = decode_hex(fixture['rlp'])
    except binascii.Error:
        normalized_fixture['rlpHex'] = fixture['rlp']

    if "sender" in fixture:
        # intentionally not normalized.
        normalized_fixture["transaction"] = fixture['transaction']
        # intentionally not normalized.
        normalized_fixture['sender'] = fixture['sender']

    return normalized_fixture


def normalize_block_header(header):
    normalized_header = {
        'bloom': big_endian_to_int(decode_hex(header['bloom'])),
        'coinbase': to_canonical_address(header['coinbase']),
        'difficulty': to_int(header['difficulty']),
        'extraData': decode_hex(header['extraData']),
        'gasLimit': to_int(header['gasLimit']),
        'gasUsed': to_int(header['gasUsed']),
        'hash': decode_hex(header['hash']),
        'mixHash': decode_hex(header['mixHash']),
        'nonce': decode_hex(header['nonce']),
        'number': to_int(header['number']),
        'parentHash': decode_hex(header['parentHash']),
        'receiptTrie': decode_hex(header['receiptTrie']),
        'stateRoot': decode_hex(header['stateRoot']),
        'timestamp': to_int(header['timestamp']),
        'transactionsTrie': decode_hex(header['transactionsTrie']),
        'uncleHash': decode_hex(header['uncleHash']),
    }
    if 'blocknumber' in header:
        normalized_header['blocknumber'] = to_int(header['blocknumber'])
    if 'chainname' in header:
        normalized_header['chainname'] = header['chainname']
    if 'chainnetwork' in header:
        normalized_header['chainnetwork'] = header['chainnetwork']
    return normalized_header


def normalize_block(block):
    normalized_block = {}

    try:
        normalized_block['rlp'] = decode_hex(block['rlp'])
    except ValueError as err:
        normalized_block['rlp_error'] = err

    if 'blockHeader' in block:
        normalized_block['blockHeader'] = normalize_block_header(block['blockHeader'])
    if 'transactions' in block:
        normalized_block['transactions'] = [
            normalize_signed_transaction(transaction)
            for transaction
            in block['transactions']
        ]
    return normalized_block


def normalize_blockchain_fixtures(fixture):
    normalized_fixture = {
        'blocks': [normalize_block(block_fixture) for block_fixture in fixture['blocks']],
        'genesisBlockHeader': normalize_block_header(fixture['genesisBlockHeader']),
        'lastblockhash': decode_hex(fixture['lastblockhash']),
        'pre': normalize_account_state(fixture['pre']),
        'postState': normalize_account_state(fixture['postState']),
    }

    if 'genesisRLP' in fixture:
        normalized_fixture['genesisRLP'] = decode_hex(fixture['genesisRLP'])

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


def verify_state_db(expected_state, state_db):
    diff = diff_state_db(expected_state, state_db)
    if diff:
        error_messages = []
        for account, field, actual_value, expected_value in diff:
            if field == 'balance':
                error_messages.append(
                    "{0}({1}) | Actual: {2} | Expected: {3} | Delta: {4}".format(
                        to_normalized_address(account),
                        'balance',
                        actual_value,
                        expected_value,
                        expected_value - actual_value,
                    )
                )
            else:
                error_messages.append(
                    "{0}({1}) | Actual: {2} | Expected: {3}".format(
                        to_normalized_address(account),
                        field,
                        actual_value,
                        expected_value,
                    )
                )
        raise AssertionError(
            "State DB did not match expected state on {0} values:\n"
            "{1}".format(
                len(error_messages),
                "\n - ".join(error_messages),
            )
        )
