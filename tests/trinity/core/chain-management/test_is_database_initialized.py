import pytest

# TODO: use a custom chain class only for testing.
from evm.chains.ropsten import ROPSTEN_GENESIS_HEADER
from evm.db.backends.level import LevelDB

from trinity.chains import (
    initialize_data_dir,
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


def test_database_dir_not_initialized_without_canonical_head_block(headerdb):
    assert not is_database_initialized(headerdb)


def test_fully_initialized_database_dir(headerdb):
    assert not is_database_initialized(headerdb)
    headerdb.persist_header(ROPSTEN_GENESIS_HEADER)
    assert is_database_initialized(headerdb)
