from pathlib import Path

import pytest

from eth_utils import (
    decode_hex,
)

from eth_keys import keys

from trinity._utils.chains import (
    DATABASE_SOCKET_FILENAME,
    get_data_dir_for_network_id,
    get_local_data_dir,
    get_nodekey_path,
    JSONRPC_SOCKET_FILENAME,
)
from trinity.config import (
    TrinityConfig,
    BeaconAppConfig,
    DATABASE_DIR_NAME,
)
from trinity.constants import (
    IPC_DIR,
    LOG_DIR,
    LOG_FILE,
    PID_DIR
)
from trinity._utils.filesystem import (
    is_under_path,
)


@pytest.mark.parametrize(
    "app_identifier, expected_suffix",
    (
        ("beacon", "-beacon"),
        ("", ""),
    ),
)
def test_trinity_config_app_identifier(xdg_trinity_root, app_identifier, expected_suffix):

    data_dir = get_local_data_dir('muffin', xdg_trinity_root)
    trinity_config = TrinityConfig(network_id=1, data_dir=data_dir, app_identifier=app_identifier)

    assert trinity_config.network_id == 1
    assert trinity_config.data_dir == data_dir
    assert trinity_config.logfile_path == data_dir / (LOG_DIR + expected_suffix) / LOG_FILE
    assert trinity_config.jsonrpc_ipc_path == data_dir / (IPC_DIR + expected_suffix) / JSONRPC_SOCKET_FILENAME  # noqa: E501
    assert trinity_config.database_ipc_path == data_dir / (IPC_DIR + expected_suffix) / DATABASE_SOCKET_FILENAME  # noqa: E501
    assert trinity_config.pid_dir == data_dir / (PID_DIR + expected_suffix)
    assert trinity_config.database_dir == data_dir / (DATABASE_DIR_NAME + expected_suffix) / "full"
    assert trinity_config.nodekey_path == get_nodekey_path(data_dir)


def test_trinity_config_computed_properties(xdg_trinity_root):
    data_dir = get_local_data_dir('muffin', xdg_trinity_root)
    trinity_config = TrinityConfig(network_id=1, data_dir=data_dir)

    assert trinity_config.network_id == 1
    assert trinity_config.data_dir == data_dir
    assert trinity_config.database_dir == data_dir / DATABASE_DIR_NAME / "full"
    assert trinity_config.nodekey_path == get_nodekey_path(data_dir)


def test_trinity_config_computed_properties_custom_xdg(tmpdir, xdg_trinity_root):
    alt_xdg_root = tmpdir.mkdir('trinity-custom')
    assert not is_under_path(alt_xdg_root, xdg_trinity_root)

    data_dir = get_data_dir_for_network_id(1, alt_xdg_root)
    trinity_config = TrinityConfig(trinity_root_dir=alt_xdg_root, network_id=1)

    assert trinity_config.network_id == 1
    assert trinity_config.data_dir == data_dir
    assert trinity_config.database_dir == data_dir / DATABASE_DIR_NAME / "full"
    assert trinity_config.nodekey_path == get_nodekey_path(data_dir)


def test_trinity_config_explicit_properties():
    trinity_config = TrinityConfig(
        network_id=1,
        data_dir='./data-dir',
        nodekey_path='./nodekey'
    )

    assert trinity_config.data_dir == Path('./data-dir').resolve()
    assert trinity_config.nodekey_path == Path('./nodekey').resolve()


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


def test_trinity_config_nodekey_loading(nodekey_bytes, nodekey_path):
    trinity_config = TrinityConfig(
        network_id=1,
        nodekey_path=nodekey_path,
    )

    assert trinity_config.nodekey.to_bytes() == nodekey_bytes


@pytest.mark.parametrize('as_bytes', (True, False))
def test_trinity_config_explictely_provided_nodekey(nodekey_bytes, as_bytes):
    trinity_config = TrinityConfig(
        network_id=1,
        nodekey=nodekey_bytes if as_bytes else keys.PrivateKey(nodekey_bytes),
    )

    assert trinity_config.nodekey.to_bytes() == nodekey_bytes


def test_trinity_config_sub_configs():
    trinity_config = TrinityConfig(network_id=1)
    trinity_config.initialize_app_configs(None, (BeaconAppConfig,))

    assert trinity_config.has_app_config(BeaconAppConfig)
    beacon_config = trinity_config.get_app_config(BeaconAppConfig)
    assert type(beacon_config) is BeaconAppConfig
