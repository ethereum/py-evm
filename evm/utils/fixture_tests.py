import binascii
import fnmatch
import functools
import hashlib
import json
import os

import rlp

import pytest

from cytoolz import (
    curry,
    identity,
)

from eth_utils import (
    decode_hex,
    is_0x_prefixed,
    keccak,
    pad_left,
    remove_0x_prefix,
    to_canonical_address,
    to_normalized_address,
    to_tuple,
    to_dict,
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


def find_fixture_files(fixtures_base_dir):
    all_fixture_paths = _recursive_find_files(fixtures_base_dir, "*.json")
    return all_fixture_paths


@to_tuple
def find_fixtures(fixtures_base_dir):
    """
    Finds all of the (fixture_path, fixture_key) pairs for a given path under
    the JSON test fixtures directory.
    """
    all_fixture_paths = find_fixture_files(fixtures_base_dir)

    for fixture_path in sorted(all_fixture_paths):
        with open(fixture_path) as fixture_file:
            fixtures = json.load(fixture_file)

        for fixture_key in sorted(fixtures.keys()):
            yield (fixture_path, fixture_key)


@curry
def filter_fixtures(all_fixtures, fixtures_base_dir, mark_fn=None, ignore_fn=None):
    """
    Helper function for filtering test fixtures.

    - `fixtures_base_dir` should be the base directory that the fixtures were collected from.
    - `mark_fn` should be a function which either returns `None` or a `pytest.mark` object.
    - `ignore_fn` should be a function which returns `True` for any fixture
       which should be ignored.
    """
    for fixture_data in all_fixtures:
        fixture_path = fixture_data[0]
        fixture_relpath = os.path.relpath(fixture_path, fixtures_base_dir)

        if ignore_fn:
            if ignore_fn(fixture_relpath, *fixture_data[1:]):
                continue

        if mark_fn is not None:
            mark = mark_fn(fixture_relpath, *fixture_data[1:])
            if mark:
                yield pytest.param(
                    (fixture_path, *fixture_data[1:]),
                    marks=mark,
                )
                continue

        yield fixture_data


def hash_log_entries(log_entries):
    """
    Helper function for computing the RLP hash of the logs from transaction
    execution.
    """
    from evm.rlp.logs import Log
    logs = [Log(*entry) for entry in log_entries]
    encoded_logs = rlp.encode(logs)
    logs_hash = keccak(encoded_logs)
    return logs_hash


# we use an LRU cache on this function so that we can sort the tests such that
# all fixtures from the same file are executed sequentially allowing us to keep
# a small rolling cache of the loaded fixture files.
@functools.lru_cache(maxsize=4)
def load_json_fixture(fixture_path):
    """
    Loads a fixture file, caching the most recent files it loaded.
    """
    with open(fixture_path) as fixture_file:
        file_fixtures = json.load(fixture_file)
    return file_fixtures


def load_fixture(fixture_path, fixture_key, normalize_fn=identity):
    """
    Loads a specific fixture from a fixture file, optionally passing it through
    a normalization function.
    """
    file_fixtures = load_json_fixture(fixture_path)
    fixture = normalize_fn(file_fixtures[fixture_key])
    return fixture


#
# RLP Diffing
#
def assert_rlp_equal(left, right):
    """
    Helper for asserting two RPL objects are equal, producing a helpful error
    message with what fields are not equal.
    """
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
# Fixture Normalization Primitives
#
@functools.lru_cache(maxsize=1024)
def to_int(value):
    """
    Robust to integer conversion, handling hex values, string representations,
    and special cases like `0x`.
    """
    if is_0x_prefixed(value):
        if len(value) == 2:
            return 0
        else:
            return int(value, 16)
    else:
        return int(value)


@functools.lru_cache(maxsize=128)
def normalize_to_address(value):
    if value:
        return to_canonical_address(value)
    else:
        return CREATE_CONTRACT_ADDRESS


def robust_decode_hex(value):
    unprefixed_value = remove_0x_prefix(value)
    if len(unprefixed_value) % 2:
        return decode_hex(pad_left(unprefixed_value, len(unprefixed_value) + 1, b'0'))
    else:
        return decode_hex(unprefixed_value)


#
# Pytest fixture generation
#
def idfn(fixture_params):
    """
    Function for pytest to produce uniform names for fixtures.
    """
    return ":".join((str(item) for item in fixture_params))


def get_fixtures_file_hash(all_fixture_paths):
    """
    Returns the MD5 hash of the fixture files.  Used for cache busting.
    """
    hasher = hashlib.md5()
    for fixture_path in sorted(all_fixture_paths):
        with open(fixture_path, 'rb') as fixture_file:
            hasher.update(fixture_file.read())
    return hasher.hexdigest()


@curry
def generate_fixture_tests(metafunc,
                           base_fixture_path,
                           filter_fn=identity,
                           preprocess_fn=identity):
    """
    Helper function for use with `pytest_generate_tests` which will use the
    pytest caching facilities to reduce the load time for fixture tests.

    - `metafunc` is the parameter from `pytest_generate_tests`
    - `base_fixture_path` is the base path that fixture files will be collected from.
    - `filter_fn` handles ignoring or marking the various fixtures.  See `filter_fixtures`.
    - `preprocess_fn` handles any preprocessing that should be done on the raw
       fixtures (such as expanding the statetest fixtures to be multiple tests for
       each fork.
    """
    fixture_namespace = os.path.basename(base_fixture_path)

    if 'fixture_data' in metafunc.fixturenames:
        all_fixture_paths = find_fixture_files(base_fixture_path)
        current_file_hash = get_fixtures_file_hash(all_fixture_paths)

        data_cache_key = 'pyevm/statetest/fixtures/{0}/data'.format(fixture_namespace)
        file_hash_cache_key = 'pyevm/statetest/fixtures/{0}/data-hash'.format(fixture_namespace)

        cached_file_hash = metafunc.config.cache.get(file_hash_cache_key, None)
        cached_fixture_data = metafunc.config.cache.get(data_cache_key, None)

        bust_cache = any((
            cached_file_hash is None,
            cached_fixture_data is None,
            cached_file_hash != current_file_hash,
        ))

        if bust_cache:
            all_fixtures = find_fixtures(base_fixture_path)

            metafunc.config.cache.set(data_cache_key, all_fixtures)
            metafunc.config.cache.set(file_hash_cache_key, current_file_hash)
        else:
            all_fixtures = cached_fixture_data

        if not len(all_fixtures):
            raise AssertionError(
                "Suspiciously found zero fixtures: {0}".format(base_fixture_path)
            )

        filtered_fixtures = filter_fn(preprocess_fn(all_fixtures))

        metafunc.parametrize('fixture_data', filtered_fixtures, ids=idfn)


#
# Fixture Normalizers
#
def normalize_env(env):
    return {
        'currentCoinbase': decode_hex(env['currentCoinbase']),
        'currentDifficulty': to_int(env['currentDifficulty']),
        'currentNumber': to_int(env['currentNumber']),
        'currentGasLimit': to_int(env['currentGasLimit']),
        'currentTimestamp': to_int(env['currentTimestamp']),
        'previousHash': decode_hex(env.get('previousHash', '00' * 32)),
    }


@to_dict
def normalize_unsigned_transaction(transaction, indexes):
    yield 'data', decode_hex(transaction['data'][indexes['data']])
    yield 'gasLimit', to_int(transaction['gasLimit'][indexes['gas']])
    yield 'gasPrice', to_int(transaction['gasPrice'])
    yield 'nonce', to_int(transaction['nonce'])

    if 'secretKey' in transaction:
        yield 'secretKey', decode_hex(transaction['secretKey'])
    elif 'v' in transaction and 'r' in transaction and 's' in transaction:
        yield 'vrs', (
            to_int(transaction['v']),
            to_int(transaction['r']),
            to_int(transaction['s']),
        )
    else:
        raise KeyError("transaction missing secret key or vrs values")

    yield 'to', normalize_to_address(transaction['to'])
    yield 'value', to_int(transaction['value'][indexes['value']])


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


@to_dict
def normalize_post_state(post_state):
    yield 'hash', decode_hex(post_state['hash'])
    if 'logs' in post_state:
        yield 'logs', decode_hex(post_state['logs'])


@curry
def normalize_statetest_fixture(fixture, fork, post_state_index):
    post_state = fixture['post'][fork][post_state_index]

    normalized_fixture = {
        'env': normalize_env(fixture['env']),
        'pre': normalize_account_state(fixture['pre']),
        'post': normalize_post_state(post_state),
        'transaction': normalize_unsigned_transaction(
            fixture['transaction'],
            post_state['indexes'],
        ),
    }

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


@to_dict
def normalize_vmtest_fixture(fixture):
    yield 'env', normalize_env(fixture['env'])
    yield 'exec', normalize_exec(fixture['exec'])
    yield 'pre', normalize_account_state(fixture['pre'])

    if 'post' in fixture:
        yield 'post', normalize_account_state(fixture['post'])

    if 'callcreates' in fixture:
        yield 'callcreates', normalize_callcreates(fixture['callcreates'])

    if 'gas' in fixture:
        yield 'gas', to_int(fixture['gas'])

    if 'out' in fixture:
        yield 'out', decode_hex(fixture['out'])

    if 'logs' in fixture:
        yield 'logs', decode_hex(fixture['logs'])


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
        'network': fixture['network'],
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
