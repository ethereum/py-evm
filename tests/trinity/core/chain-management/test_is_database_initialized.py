import pytest

# TODO: use a custom chain class only for testing.
from evm.chains.ropsten import ROPSTEN_GENESIS_HEADER
from evm.db.backends.level import LevelDB
from evm.db.chain import ChainDB

from trinity.chains import (
    initialize_data_dir,
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


def test_database_dir_not_initialized_without_canonical_head_block(chaindb):
    assert not is_database_initialized(chaindb)


def test_fully_initialized_database_dir(chaindb):
    assert not is_database_initialized(chaindb)
    chaindb.persist_header(ROPSTEN_GENESIS_HEADER)
    assert is_database_initialized(chaindb)
