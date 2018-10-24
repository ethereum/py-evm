import pytest

from trinity.initialization import (
    is_data_dir_initialized,
    initialize_data_dir,
)
from trinity.config import (
    TrinityConfig,
)


@pytest.fixture
def trinity_config():
    return TrinityConfig(network_id=1)


@pytest.fixture
def data_dir(trinity_config):
    trinity_config.data_dir.mkdir(parents=True, exist_ok=True)
    assert trinity_config.data_dir.exists()
    return trinity_config.data_dir


@pytest.fixture
def database_dir(trinity_config, data_dir):
    trinity_config.database_dir.mkdir(parents=True, exist_ok=True)
    assert trinity_config.database_dir.exists()
    return trinity_config.database_dir


@pytest.fixture
def database_engine_marker(trinity_config, database_dir):
    with trinity_config.database_engine_marker_path.open('w') as engine_marker_file:
        engine_marker_file.write(trinity_config.db_engine)

    assert trinity_config.database_engine_marker_path.exists()
    return trinity_config.database_engine_marker_path


@pytest.fixture
def nodekey(trinity_config, data_dir):
    with trinity_config.nodekey_path.open('wb') as nodekey_file:
        nodekey_file.write(b'\x01' * 32)
    return trinity_config.nodekey_path


def test_initializing_data_dir_from_nothing(trinity_config):
    assert not trinity_config.data_dir.exists()
    assert not is_data_dir_initialized(trinity_config)

    initialize_data_dir(trinity_config)

    assert is_data_dir_initialized(trinity_config)


def test_initializing_data_dir_from_empty_data_dir(trinity_config, data_dir):
    assert not trinity_config.database_dir.exists()
    assert not is_data_dir_initialized(trinity_config)

    initialize_data_dir(trinity_config)

    assert is_data_dir_initialized(trinity_config)


def test_initializing_data_dir_with_missing_engine_marker(trinity_config, database_dir):
    assert trinity_config.database_dir.exists()
    assert not trinity_config.database_engine_marker_path.exists()
    assert not is_data_dir_initialized(trinity_config)

    initialize_data_dir(trinity_config)

    assert is_data_dir_initialized(trinity_config)


def test_initializing_data_dir_with_missing_nodekey(
        trinity_config,
        data_dir,
        database_dir,
        database_engine_marker):
    assert not trinity_config.nodekey_path.exists()
    assert not is_data_dir_initialized(trinity_config)

    initialize_data_dir(trinity_config)

    assert is_data_dir_initialized(trinity_config)
