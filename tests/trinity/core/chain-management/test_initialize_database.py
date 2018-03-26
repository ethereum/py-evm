import pytest

from evm.db.backends.level import LevelDB
from evm.db.chain import ChainDB

from trinity.chains import (
    initialize_data_dir,
    initialize_database,
    is_database_initialized,
)
from trinity.utils.chains import (
    ChainConfig,
    PRECONFIGURED_NETWORKS,
    get_local_data_dir,
)


@pytest.fixture(params=tuple(PRECONFIGURED_NETWORKS.keys()))
def preconfigured_chain_config(request):
    _chain_config = ChainConfig(network_id=request.param)
    initialize_data_dir(_chain_config)
    return _chain_config


def test_initialize_database_for_preconfigured_network(preconfigured_chain_config):
    chain_config = preconfigured_chain_config
    chaindb = ChainDB(LevelDB(db_path=chain_config.database_dir))

    assert not is_database_initialized(chaindb)
    initialize_database(chain_config, chaindb)
    assert is_database_initialized(chaindb)


@pytest.fixture
def custom_network_chain_config(custom_network_genesis_params):
    _chain_config = ChainConfig(
        network_id=42,
        genesis_params=custom_network_genesis_params,
        data_dir=get_local_data_dir('methuselah'),
    )
    initialize_data_dir(_chain_config)
    return _chain_config


def test_initialize_database_for_custom_network(custom_network_chain_config):
    chain_config = custom_network_chain_config
    chaindb = ChainDB(LevelDB(db_path=chain_config.database_dir))

    assert not is_database_initialized(chaindb)
    initialize_database(chain_config, chaindb)
    assert is_database_initialized(chaindb)
