import pytest

from eth_utils import (
    to_int,
    to_hex,
    to_bytes,
    to_canonical_address,
)
from eth_utils.curried import (
    hexstr_if_str,
)
from eth_utils.toolz import (
    merge,
    valmap,
)

from trinity._utils.eip1085 import (
    GenesisParams,
    extract_genesis_params,
)


PARAMS_DEFAULTS = {
    "nonce": "0x0000000000000042",
    "difficulty": "0x020000",
    "author": "0x0000000000000000000000000000000000000000",
    "timestamp": "0x00",
    "extraData": "0x11bbe8db4e347b4e8c937c1c8370e4b5ed33adb3db69cbdb7a38e1e50b1b82fa",
    "gasLimit": "0x1388"
}
N_PARAMS_DEFAULTS = {
    "nonce": to_bytes(hexstr=PARAMS_DEFAULTS['nonce']),
    "difficulty": to_int(hexstr=PARAMS_DEFAULTS['difficulty']),
    "coinbase": to_canonical_address(PARAMS_DEFAULTS['author']),
    "timestamp": to_int(hexstr=PARAMS_DEFAULTS['timestamp']),
    "extra_data": to_bytes(hexstr=PARAMS_DEFAULTS['extraData']),
    "gas_limit": to_int(hexstr=PARAMS_DEFAULTS['gasLimit']),
}


ADDRESS = b'12345678901234567890'
HASH32 = b'unicornsrainbows' * 2


def _mk_raw_params(**kwargs):
    return {
        'genesis': merge(PARAMS_DEFAULTS, valmap(hexstr_if_str(to_hex), kwargs)),
    }


def _mk_params(**kwargs):
    return GenesisParams(**merge(N_PARAMS_DEFAULTS, kwargs))


@pytest.mark.parametrize(
    'raw_genesis_config,expected',
    (
        (_mk_raw_params(), _mk_params()),
        (_mk_raw_params(nonce=b'unicorns'), _mk_params(nonce=b'unicorns')),
        (_mk_raw_params(difficulty=1234), _mk_params(difficulty=1234)),
        (_mk_raw_params(author=ADDRESS), _mk_params(coinbase=ADDRESS)),
        (_mk_raw_params(timestamp=1234), _mk_params(timestamp=1234)),
        (_mk_raw_params(extraData=HASH32), _mk_params(extra_data=HASH32)),
        (_mk_raw_params(gasLimit=1234), _mk_params(gas_limit=1234)),
    ),
)
def test_extract_genesis_params(raw_genesis_config, expected):
    actual = extract_genesis_params(raw_genesis_config)
    assert actual == expected
