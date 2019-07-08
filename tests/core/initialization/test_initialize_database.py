import pytest

from eth.db.backends.level import LevelDB
from eth.db.chain import ChainDB

from trinity.initialization import (
    initialize_database,
    is_database_initialized,
)


@pytest.fixture
def base_db(eth1_app_config):
    return LevelDB(db_path=eth1_app_config.database_dir)


@pytest.fixture
def chaindb(base_db):
    return ChainDB(base_db)


def test_initialize_database(eth1_app_config, chaindb, base_db):
    assert not is_database_initialized(chaindb)
    initialize_database(eth1_app_config.get_chain_config(), chaindb, base_db)
    assert is_database_initialized(chaindb)
