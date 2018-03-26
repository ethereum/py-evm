import pytest

from eth_utils import (
    decode_hex,
)

from eth_keys import keys

from trinity.utils.chains import (
    get_local_data_dir,
    get_database_dir,
    get_nodekey_path,
    ChainConfig,
    DEFAULT_DATA_DIRS,
    PRECONFIGURED_NETWORKS,
)
from trinity.utils.filesystem import (
    is_same_path,
)


@pytest.fixture(params=tuple(PRECONFIGURED_NETWORKS.keys()))
def preconfigured_network_id(request):
    return request.param


def test_chain_config_computed_properties_on_preconfigured_network(preconfigured_network_id):
    network_id = preconfigured_network_id
    data_dir = get_local_data_dir(DEFAULT_DATA_DIRS[network_id])
    chain_config = ChainConfig(network_id=network_id, data_dir=data_dir)

    assert chain_config.network_id == network_id
    assert chain_config.data_dir == data_dir
    assert chain_config.database_dir == get_database_dir(data_dir)
    assert chain_config.nodekey_path == get_nodekey_path(data_dir)


def test_chain_config_explicit_properties(preconfigured_network_id):
    network_id = preconfigured_network_id
    chain_config = ChainConfig(
        network_id=network_id,
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


def test_chain_config_nodekey_loading(nodekey_bytes, nodekey_path, preconfigured_network_id):
    network_id = preconfigured_network_id
    chain_config = ChainConfig(
        network_id=network_id,
        nodekey_path=nodekey_path,
    )

    assert chain_config.nodekey.to_bytes() == nodekey_bytes


@pytest.mark.parametrize('as_bytes', (True, False))
def test_chain_config_explictely_provided_nodekey(nodekey_bytes,
                                                  as_bytes,
                                                  preconfigured_network_id):
    network_id = preconfigured_network_id
    chain_config = ChainConfig(
        network_id=network_id,
        nodekey=nodekey_bytes if as_bytes else keys.PrivateKey(nodekey_bytes),
    )

    assert chain_config.nodekey.to_bytes() == nodekey_bytes


def test_chain_config_computed_properties_on_custom_network(custom_network_genesis_params):
    data_dir = get_local_data_dir('muffin')
    chain_config = ChainConfig(
        network_id=42,
        data_dir=data_dir,
        genesis_params=custom_network_genesis_params,
    )

    assert chain_config.network_id == 42
    assert chain_config.data_dir == data_dir
    assert chain_config.database_dir == get_database_dir(data_dir)
    assert chain_config.nodekey_path == get_nodekey_path(data_dir)

    assert custom_network_genesis_params == chain_config.genesis_params
