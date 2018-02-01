import pytest

from eth_keys import keys

from trinity.utils.chains import (
    get_default_data_dir,
    get_database_dir,
    get_nodekey_path,
    ChainConfig,
)
from trinity.utils.hexadecimal import (
    decode_hex,
)
from trinity.utils.filesystem import (
    is_same_path,
)


def test_chain_config_computed_properties():
    chain_config = ChainConfig('muffin')

    assert chain_config.data_dir == get_default_data_dir('muffin')
    assert chain_config.database_dir == get_database_dir('muffin')
    assert chain_config.nodekey_path == get_nodekey_path('muffin')


def test_chain_config_explicit_properties():
    chain_config = ChainConfig(
        'muffin',
        data_dir='./data-dir',
        nodekey_path='./nodekey'
    )

    assert is_same_path(chain_config.data_dir, './data-dir')
    assert is_same_path(chain_config.nodekey_path, './nodekey')


NODEKEY = '0xd18445cc77139cd8e09110e99c9384f0601bd2dfa5b230cda917df7e56b69949'


@pytest.fixture
def nodekey_bytes():
    _nodekey_bytes = decode_hex(NODEKEY)
    return _nodekey_bytes


@pytest.fixture
def nodekey_path(tmpdir, nodekey_bytes):
    nodekey_file = tmpdir.mkdir('temp-nodekey-dir').join('nodekey')
    nodekey_file.write_binary(nodekey_bytes)

    return str(nodekey_file)


def test_chain_config_nodekey_loading(nodekey_bytes, nodekey_path):
    chain_config = ChainConfig(
        'muffin',
        nodekey_path=nodekey_path,
    )

    assert chain_config.nodekey.to_bytes() == nodekey_bytes


@pytest.mark.parametrize('as_bytes', (True, False))
def test_chain_config_explictely_provided_nodekey(nodekey_bytes, as_bytes):
    chain_config = ChainConfig(
        'muffin',
        nodekey=nodekey_bytes if as_bytes else keys.PrivateKey(nodekey_bytes),
    )

    assert chain_config.nodekey.to_bytes() == nodekey_bytes
