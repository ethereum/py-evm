import os
import pytest

from eth_utils import decode_hex

from trinity.chains import (
    is_data_dir_initialized,
)
from trinity.config import (
    ChainConfig,
)


@pytest.fixture
def chain_config():
    return ChainConfig(network_id=1)


@pytest.fixture
def data_dir(chain_config):
    os.makedirs(chain_config.data_dir, exist_ok=True)
    assert os.path.exists(chain_config.data_dir)
    return chain_config.data_dir


@pytest.fixture
def logfile_dir(chain_config):
    chain_config.logfile_path.parent.mkdir(parents=True)
    return chain_config.logfile_path.parent


@pytest.fixture
def logfile_path(chain_config, logfile_dir):
    chain_config.logfile_path.touch()
    return chain_config.logfile_path


@pytest.fixture
def database_dir(chain_config, data_dir):
    os.makedirs(chain_config.database_dir, exist_ok=True)
    assert os.path.exists(chain_config.database_dir)
    return chain_config.database_dir


@pytest.fixture
def nodekey(chain_config, data_dir):
    with open(chain_config.nodekey_path, 'wb') as nodekey_file:
        nodekey_file.write(b'\x01' * 32)
    return chain_config.nodekey_path


def test_not_initialized_without_data_dir(chain_config):
    assert not os.path.exists(chain_config.data_dir)
    assert not is_data_dir_initialized(chain_config)


def test_not_initialized_without_database_dir(chain_config, data_dir):
    assert not os.path.exists(chain_config.database_dir)
    assert not is_data_dir_initialized(chain_config)


def test_not_initialized_without_nodekey_file(chain_config, data_dir, database_dir):
    assert not os.path.exists(chain_config.nodekey_path)
    assert not is_data_dir_initialized(chain_config)


def test_not_initialized_without_logfile_dir(chain_config, data_dir, database_dir, nodekey):
    assert not os.path.exists(chain_config.logfile_path.parent)
    assert not is_data_dir_initialized(chain_config)


def test_not_initialized_without_logfile_path(
        chain_config,
        data_dir,
        database_dir,
        nodekey,
        logfile_dir):
    assert not os.path.exists(chain_config.logfile_path)
    assert not is_data_dir_initialized(chain_config)


def test_full_initialized_data_dir(
        chain_config,
        data_dir,
        database_dir,
        nodekey,
        logfile_dir,
        logfile_path):
    assert is_data_dir_initialized(chain_config)


NODEKEY = decode_hex('0xd18445cc77139cd8e09110e99c9384f0601bd2dfa5b230cda917df7e56b69949')


def test_full_initialized_data_dir_with_custom_nodekey():
    chain_config = ChainConfig(network_id=1, nodekey=NODEKEY)

    os.makedirs(chain_config.data_dir, exist_ok=True)
    os.makedirs(chain_config.database_dir, exist_ok=True)
    os.makedirs(chain_config.logfile_path, exist_ok=True)
    chain_config.logfile_path.touch()

    assert chain_config.nodekey_path is None
    assert chain_config.nodekey is not None

    assert is_data_dir_initialized(chain_config)
