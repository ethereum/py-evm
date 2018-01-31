import pytest

import os

from evm.chains.ropsten import ROPSTEN_GENESIS_HEADER

from trinity.chains import (
    is_chain_initialized,
)
from trinity.chains.ropsten import (
    RopstenLightChain,
)
from trinity.utils.chains import (
    ChainConfig,
)
from trinity.utils.db import (
    get_chain_db,
)


@pytest.fixture
def chain_config():
    return ChainConfig('test_chain')


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


def test_not_initialized_without_data_dir(chain_config):
    assert not os.path.exists(chain_config.data_dir)
    assert not is_chain_initialized(chain_config)


def test_not_initialized_without_database_dir(chain_config, data_dir):
    assert not os.path.exists(chain_config.database_dir)
    assert not is_chain_initialized(chain_config)


def test_not_initialized_without_nodekey_file(chain_config, data_dir, database_dir):
    assert not os.path.exists(chain_config.nodekey_path)
    assert not is_chain_initialized(chain_config)


def test_not_initialized_without_initialized_chaindb(chain_config,
                                                     data_dir,
                                                     database_dir,
                                                     nodekey):
    assert os.path.exists(chain_config.data_dir)
    assert os.path.exists(chain_config.database_dir)
    assert chain_config.nodekey is not None

    assert not is_chain_initialized(chain_config)


def test_fully_initialized_chain_datadir(chain_config,
                                         data_dir,
                                         database_dir,
                                         nodekey):
    # Database Initialization
    chaindb = get_chain_db(chain_config.data_dir)
    RopstenLightChain.from_genesis_header(chaindb, ROPSTEN_GENESIS_HEADER)

    # we need to delete the chaindb in order to release the leveldb LOCK.
    del chaindb

    assert is_chain_initialized(chain_config)
