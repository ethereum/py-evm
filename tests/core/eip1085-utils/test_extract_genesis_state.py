import pytest

from eth_utils import (
    encode_hex,
)

from trinity._utils.eip1085 import (
    Account,
    extract_genesis_state,
)


ADDRESS = b'01' * 10
ADDRESS_HEX = encode_hex(ADDRESS)

ACCOUNT_EMPTY = {
    'balance': '0x00',
    'nonce': '0x00',
    'code': '',
    'storage': {},
}
N_ACCOUNT_EMPTY = Account(**{
    'balance': 0,
    'nonce': 0,
    'code': b'',
    'storage': {},
})

ACCOUNT_SIMPLE = {
    'balance': '0x10',
    'nonce': '0x20',
    'code': '0x74657374',
    'storage': {},
}
N_ACCOUNT_SIMPLE = Account(**{
    'balance': 16,
    'nonce': 32,
    'code': b'test',
    'storage': {},
})

ACCOUNT_STORAGE = {
    'balance': '0x10',
    'nonce': '0x20',
    'code': '',
    'storage': {'0x01': '0x74657374'},
}
N_ACCOUNT_STORAGE = Account(**{
    'balance': 16,
    'nonce': 32,
    'code': b'',
    'storage': {1: 1952805748},
})


@pytest.mark.parametrize(
    'genesis_config,expected',
    (
        ({}, {}),
        ({'accounts': {}}, {}),
        ({'accounts': {ADDRESS_HEX: ACCOUNT_EMPTY}}, {ADDRESS: N_ACCOUNT_EMPTY}),
        ({'accounts': {ADDRESS_HEX: ACCOUNT_SIMPLE}}, {ADDRESS: N_ACCOUNT_SIMPLE}),
        ({'accounts': {ADDRESS_HEX: ACCOUNT_STORAGE}}, {ADDRESS: N_ACCOUNT_STORAGE}),
    ),
)
def test_eip1085_extract_genesis_state(genesis_config, expected):
    actual = extract_genesis_state(genesis_config)
    assert actual == expected
