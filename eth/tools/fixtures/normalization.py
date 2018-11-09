import binascii
import functools

from typing import (
    Any,
    AnyStr,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Sequence,
    Tuple,
)

from cytoolz import (
    assoc_in,
    compose,
    concat,
    curry,
    identity,
    merge,
)
import cytoolz.curried

from eth_typing import (
    Address,
)

from eth_utils import (
    apply_formatters_to_dict,
    big_endian_to_int,
    decode_hex,
    is_0x_prefixed,
    is_bytes,
    is_hex,
    is_integer,
    is_string,
    is_text,
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
from eth.tools._utils.normalization import (
    normalize_transaction_group,
    normalize_environment,
    to_int,
)

from eth.typing import (
    AccountState,
    GeneralState,
    Normalizer,
    TransactionDict,
)


#
# Primitives
#
def normalize_bytes(value: Any) -> bytes:
    if is_bytes(value):
        return value
    elif is_text(value) and is_hex(value):
        return decode_hex(value)
    else:
        raise TypeError("Value must be either a string or bytes object")


robust_decode_hex = eth_utils.curried.hexstr_if_str(to_bytes)


#
# Fixture Normalizers
#
def normalize_unsigned_transaction(transaction: TransactionDict,
                                   indexes: Dict[str, Any]) -> TransactionDict:

    normalized = normalize_transaction_group(transaction)
    return merge(normalized, {
        # Dynamic key access not yet allowed with TypedDict
        # https://github.com/python/mypy/issues/5359
        transaction_key: normalized[transaction_key][indexes[index_key]]  # type: ignore
        for transaction_key, index_key in [
            ("gasLimit", "gas"),
            ("value", "value"),
            ("data", "data"),
        ]
        if index_key in indexes
    })


def normalize_account_state(account_state: AccountState) -> AccountState:
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
def normalize_post_state(post_state: Dict[str, Any]) -> Iterable[Tuple[str, bytes]]:
    yield 'hash', decode_hex(post_state['hash'])
    if 'logs' in post_state:
        yield 'logs', decode_hex(post_state['logs'])


@curry
def normalize_statetest_fixture(fixture: Dict[str, Any],
                                fork: str,
                                post_state_index: int) -> Dict[str, Any]:

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


def normalize_exec(exec_params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'origin': to_canonical_address(exec_params['origin']),
        'address': to_canonical_address(exec_params['address']),
        'caller': to_canonical_address(exec_params['caller']),
        'value': to_int(exec_params['value']),
        'data': decode_hex(exec_params['data']),
        'gas': to_int(exec_params['gas']),
        'gasPrice': to_int(exec_params['gasPrice']),
    }


def normalize_callcreates(callcreates: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
def normalize_vmtest_fixture(fixture: Dict[str, Any]) -> Iterable[Tuple[str, Any]]:
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


def normalize_signed_transaction(transaction: Dict[str, Any]) -> Dict[str, Any]:
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
def normalize_transactiontest_fixture(fixture: Dict[str, Any], fork: str) -> Dict[str, Any]:

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


def normalize_block_header(header: Dict[str, Any]) -> Dict[str, Any]:
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


def normalize_block(block: Dict[str, Any]) -> Dict[str, Any]:
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


def normalize_blockchain_fixtures(fixture: Dict[str, Any]) -> Dict[str, Any]:
    normalized_fixture = {
        'blocks': [normalize_block(block_fixture) for block_fixture in fixture['blocks']],
        'genesisBlockHeader': normalize_block_header(fixture['genesisBlockHeader']),
        'lastblockhash': decode_hex(fixture['lastblockhash']),
        'pre': normalize_account_state(fixture['pre']),
        'postState': normalize_account_state(fixture['postState']),
        'network': fixture['network'],
    }

    if 'sealEngine' in fixture:
        normalized_fixture['sealEngine'] = fixture['sealEngine']

    if 'genesisRLP' in fixture:
        normalized_fixture['genesisRLP'] = decode_hex(fixture['genesisRLP'])

    return normalized_fixture
