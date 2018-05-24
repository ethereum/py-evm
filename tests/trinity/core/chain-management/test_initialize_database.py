import pytest

# TODO: use a custom chain class only for testing.
from evm.db.backends.level import LevelDB
from evm.db.chain import ChainDB

from trinity.chains import (
    initialize_data_dir,
    initialize_database,
    is_database_initialized,
)
from trinity.config import (
    ChainConfig,
)


@pytest.fixture
def chain_config():
    _chain_config = ChainConfig(network_id=1)
    initialize_data_dir(_chain_config)
    return _chain_config


@pytest.fixture
def chaindb(chain_config):
    return ChainDB(LevelDB(db_path=chain_config.database_dir))


def test_initialize_database(chain_config, chaindb):
    assert not is_database_initialized(chaindb)
    initialize_database(chain_config, chaindb)
    assert is_database_initialized(chaindb)
