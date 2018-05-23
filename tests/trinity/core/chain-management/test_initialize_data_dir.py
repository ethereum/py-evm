import pytest

import os

from trinity.chains import (
    ChainConfig,
    is_data_dir_initialized,
    initialize_data_dir,
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
def database_dir(chain_config, data_dir):
    os.makedirs(chain_config.database_dir, exist_ok=True)
    assert os.path.exists(chain_config.database_dir)
    return chain_config.database_dir


@pytest.fixture
def nodekey(chain_config, data_dir):
    with open(chain_config.nodekey_path, 'wb') as nodekey_file:
        nodekey_file.write(b'\x01' * 32)
    return chain_config.nodekey_path


def test_initializing_data_dir_from_nothing(chain_config):
    assert not os.path.exists(chain_config.data_dir)
    assert not is_data_dir_initialized(chain_config)

    initialize_data_dir(chain_config)

    assert is_data_dir_initialized(chain_config)


def test_initializing_data_dir_from_empty_data_dir(chain_config, data_dir):
    assert not os.path.exists(chain_config.database_dir)
    assert not is_data_dir_initialized(chain_config)

    initialize_data_dir(chain_config)

    assert is_data_dir_initialized(chain_config)


def test_initializing_data_dir_with_missing_nodekey(chain_config, data_dir, database_dir):
    assert not os.path.exists(chain_config.nodekey_path)
    assert not is_data_dir_initialized(chain_config)

    initialize_data_dir(chain_config)

    assert is_data_dir_initialized(chain_config)
