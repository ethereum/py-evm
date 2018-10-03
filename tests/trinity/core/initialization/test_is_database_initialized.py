import pytest

# TODO: use a custom chain class only for testing.
from eth.chains.ropsten import ROPSTEN_GENESIS_HEADER
from eth.db.backends.level import LevelDB
from eth.db.chain import ChainDB

from trinity.initialization import (
    initialize_data_dir,
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


def test_database_dir_not_initialized_without_canonical_head_block(chaindb):
    assert not is_database_initialized(chaindb)


def test_fully_initialized_database_dir(chaindb):
    assert not is_database_initialized(chaindb)
    chaindb.persist_header(ROPSTEN_GENESIS_HEADER)
    assert is_database_initialized(chaindb)
