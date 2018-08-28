import binascii
from collections.abc import (
    Iterable,
    Mapping,
)
import functools

from cytoolz import (
    assoc_in,
    compose,
    concat,
    curry,
    identity,
    merge,
)
import cytoolz.curried

from eth_utils import (
    apply_formatters_to_dict,
    big_endian_to_int,
    decode_hex,
    is_0x_prefixed,
    is_bytes,
    is_hex,
    is_integer,
    is_string,
    to_bytes,
    to_canonical_address,
    to_dict,
    ValidationError,
)
import eth_utils.curried

from eth.constants import (
    CREATE_CONTRACT_ADDRESS,
)

from eth.tools._utils.mappings import (
    deep_merge,
    is_cleanly_mergable,
)


#
# Primitives
#
@functools.lru_cache(maxsize=1024)
def normalize_int(value):
    """
    Robust to integer conversion, handling hex values, string representations,
    and special cases like `0x`.
    """
    if is_integer(value):
        return value
    elif is_bytes(value):
        return big_endian_to_int(value)
    elif is_hex(value) and is_0x_prefixed(value):
        if len(value) == 2:
            return 0
        else:
            return int(value, 16)
    elif is_string(value):
        return int(value)
    else:
        raise TypeError("Unsupported type: Got `{0}`".format(type(value)))


def normalize_bytes(value):
    if is_hex(value) or len(value) == 0:
        return decode_hex(value)
    elif is_bytes(value):
        return value
    else:
        raise TypeError("Value must be either a string or bytes object")


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


robust_decode_hex = eth_utils.curried.hexstr_if_str(to_bytes)


#
# Containers
#
def dict_normalizer(formatters, required=None, optional=None):
    all_keys = set(formatters.keys())

    if required is None and optional is None:
        required = all_keys
    elif required is not None:
        required = set(required)
    elif optional is not None:
        required = all_keys - set(optional)
    else:
        raise ValueError("Both required and optional keys specified")

    def normalizer(d):
        keys = set(d.keys())
        missing_keys = required - keys
        superfluous_keys = keys - all_keys
        if missing_keys:
            raise KeyError("Missing required keys: {}".format(", ".join(missing_keys)))
        if superfluous_keys:
            raise KeyError("Superfluous keys: {}".format(", ".join(superfluous_keys)))

        return apply_formatters_to_dict(formatters, d)

    return normalizer


def dict_options_normalizer(normalizers):

    def normalize(d):
        first_exception = None
        for normalizer in normalizers:
            try:
                normalized = normalizer(d)
            except KeyError as e:
                if not first_exception:
                    first_exception = e
            else:
                return normalized
        assert first_exception is not None
        raise first_exception

    return normalize


#
# Composition
#
def state_definition_to_dict(state_definition):
    """Convert a state definition to the canonical dict form.

    State can either be defined in the canonical form, or as a list of sub states that are then
    merged to one. Sub states can either be given as dictionaries themselves, or as tuples where
    the last element is the value and all others the keys for this value in the nested state
    dictionary. Example:

    ```
        [
            ("0xaabb", "balance", 3),
            ("0xaabb", "storage", {
                4: 5,
            }),
            "0xbbcc", {
                "balance": 6,
                "nonce": 7
            }
        ]
    ```
    """
    if isinstance(state_definition, Mapping):
        state_dict = state_definition
    elif isinstance(state_definition, Iterable):
        state_dicts = [
            assoc_in(
                {},
                state_item[:-1],
                state_item[-1]
            ) if not isinstance(state_item, Mapping) else state_item
            for state_item
            in state_definition
        ]
        if not is_cleanly_mergable(*state_dicts):
            raise ValidationError("Some state item is defined multiple times")
        state_dict = deep_merge(*state_dicts)
    else:
        assert TypeError("State definition must either be a mapping or a sequence")

    seen_keys = set(concat(d.keys() for d in state_dict.values()))
    bad_keys = seen_keys - set(["balance", "nonce", "storage", "code"])
    if bad_keys:
        raise ValidationError(
            "State definition contains the following invalid account fields: {}".format(
                ", ".join(bad_keys)
            )
        )

    return state_dict


normalize_storage = compose(
    cytoolz.curried.keymap(normalize_int),
    cytoolz.curried.valmap(normalize_int),
)


normalize_state = compose(
    cytoolz.curried.keymap(to_canonical_address),
    cytoolz.curried.valmap(dict_normalizer({
        "balance": normalize_int,
        "code": normalize_bytes,
        "nonce": normalize_int,
        "storage": normalize_storage
    }, required=[])),
    eth_utils.curried.apply_formatter_if(
        lambda s: isinstance(s, Iterable) and not isinstance(s, Mapping),
        state_definition_to_dict
    ),
)


normalize_main_transaction = dict_normalizer({
    "data": normalize_bytes,
    "gasLimit": normalize_int,
    "gasPrice": normalize_int,
    "nonce": normalize_int,
    "secretKey": normalize_bytes,
    "to": normalize_to_address,
    "value": normalize_int,
})


normalize_transaction = dict_options_normalizer([
    normalize_main_transaction,
])


normalize_main_transaction_group = dict_normalizer({
    "data": eth_utils.curried.apply_formatter_to_array(normalize_bytes),
    "gasLimit": eth_utils.curried.apply_formatter_to_array(normalize_int),
    "gasPrice": normalize_int,
    "nonce": normalize_int,
    "secretKey": normalize_bytes,
    "to": normalize_to_address,
    "value": eth_utils.curried.apply_formatter_to_array(normalize_int),
})


normalize_transaction_group = dict_options_normalizer([
    normalize_main_transaction_group,
])


normalize_execution = dict_normalizer({
    "address": to_canonical_address,
    "origin": to_canonical_address,
    "caller": to_canonical_address,
    "value": normalize_int,
    "data": normalize_bytes,
    "gasPrice": normalize_int,
    "gas": normalize_int,
})


normalize_networks = identity


normalize_call_create_item = dict_normalizer({
    "data": normalize_bytes,
    "destination": to_canonical_address,
    "gasLimit": normalize_int,
    "value": normalize_int,
})
normalize_call_creates = eth_utils.curried.apply_formatter_to_array(normalize_call_create_item)

normalize_log_item = dict_normalizer({
    "address": to_canonical_address,
    "topics": eth_utils.curried.apply_formatter_to_array(normalize_int),
    "data": normalize_bytes,
})
normalize_logs = eth_utils.curried.apply_formatter_to_array(normalize_log_item)


normalize_main_environment = dict_normalizer({
    "currentCoinbase": to_canonical_address,
    "previousHash": normalize_bytes,
    "currentNumber": normalize_int,
    "currentDifficulty": normalize_int,
    "currentGasLimit": normalize_int,
    "currentTimestamp": normalize_int,
}, optional=["previousHash"])


normalize_environment = dict_options_normalizer([
    normalize_main_environment,
])


#
# Fixture Normalizers
#
def normalize_unsigned_transaction(transaction, indexes):
    normalized = normalize_transaction_group(transaction)
    return merge(normalized, {
        transaction_key: normalized[transaction_key][indexes[index_key]]
        for transaction_key, index_key in [
            ("gasLimit", "gas"),
            ("value", "value"),
            ("data", "data"),
        ]
        if index_key in indexes
    })


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
        'env': normalize_environment(fixture['env']),
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
    yield 'env', normalize_environment(fixture['env'])
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


@curry
def normalize_transactiontest_fixture(fixture, fork):

    normalized_fixture = {}

    fork_data = fixture[fork]

    try:
        normalized_fixture['rlp'] = decode_hex(fixture['rlp'])
    except binascii.Error:
        normalized_fixture['rlpHex'] = fixture['rlp']

    if "sender" in fork_data:
        normalized_fixture['sender'] = fork_data['sender']

    if "hash" in fork_data:
        normalized_fixture['hash'] = fork_data['hash']

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
