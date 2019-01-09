import pytest

# TODO: use a custom chain class only for testing.
from eth.chains.ropsten import ROPSTEN_GENESIS_HEADER
from eth.db.backends.level import LevelDB
from eth.db.chain import ChainDB

from trinity.initialization import (
    is_database_initialized,
)


@pytest.fixture
def chaindb(eth1_app_config):
    return ChainDB(LevelDB(db_path=eth1_app_config.database_dir))


def test_database_dir_not_initialized_without_canonical_head_block(chaindb):
    assert not is_database_initialized(chaindb)


def test_fully_initialized_database_dir(chaindb):
    assert not is_database_initialized(chaindb)
    chaindb.persist_header(ROPSTEN_GENESIS_HEADER)
    assert is_database_initialized(chaindb)
