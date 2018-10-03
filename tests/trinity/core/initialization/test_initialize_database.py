import pytest

# TODO: use a custom chain class only for testing.
from eth.db.backends.level import LevelDB
from eth.db.chain import ChainDB

from trinity.initialization import (
    initialize_data_dir,
    initialize_database,
    is_database_initialized,
)
from trinity.config import (
    TrinityConfig,
)


@pytest.fixture
def trinity_config():
    _trinity_config = TrinityConfig(network_id=1)
    initialize_data_dir(_trinity_config)
    return _trinity_config


@pytest.fixture
def chaindb(trinity_config):
    return ChainDB(LevelDB(db_path=trinity_config.database_dir))


def test_initialize_database(trinity_config, chaindb):
    assert not is_database_initialized(chaindb)
    initialize_database(trinity_config, chaindb)
    assert is_database_initialized(chaindb)
