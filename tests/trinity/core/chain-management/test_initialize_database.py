import pytest

from evm.db.backends.level import LevelDB

from trinity.chains import (
    initialize_data_dir,
    initialize_database,
    is_database_initialized,
)
from trinity.db.header import (
    AsyncHeaderDB,
)
from trinity.utils.chains import (
    ChainConfig,
)


@pytest.fixture
def chain_config():
    _chain_config = ChainConfig(network_id=1)
    initialize_data_dir(_chain_config)
    return _chain_config


@pytest.fixture
def headerdb(chain_config):
    return AsyncHeaderDB(LevelDB(db_path=chain_config.database_dir))


def test_initialize_database(chain_config, headerdb):
    assert not is_database_initialized(headerdb)
    initialize_database(chain_config, headerdb)
    assert is_database_initialized(headerdb)
