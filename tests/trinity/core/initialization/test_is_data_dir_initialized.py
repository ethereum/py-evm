import pytest

from eth_utils import decode_hex

from trinity.initialization import (
    is_data_dir_initialized,
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
def logfile_dir(trinity_config):
    trinity_config.logfile_path.parent.mkdir(parents=True)
    return trinity_config.logfile_path.parent


@pytest.fixture
def logfile_path(trinity_config, logfile_dir):
    trinity_config.logfile_path.touch()
    return trinity_config.logfile_path


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


def test_not_initialized_without_data_dir(trinity_config):
    assert not trinity_config.data_dir.exists()
    assert not is_data_dir_initialized(trinity_config)


def test_not_initialized_without_database_dir(trinity_config, data_dir):
    assert not trinity_config.database_dir.exists()
    assert not is_data_dir_initialized(trinity_config)


def test_not_initialized_without_database_engine_marker(trinity_config, database_dir):
    assert trinity_config.database_dir.exists()
    assert not trinity_config.database_engine_marker_path.exists()
    assert not is_data_dir_initialized(trinity_config)


def test_not_initialized_without_nodekey_file(
        trinity_config,
        data_dir,
        database_dir,
        database_engine_marker):
    assert not trinity_config.nodekey_path.exists()
    assert not is_data_dir_initialized(trinity_config)


def test_not_initialized_without_logfile_dir(
        trinity_config,
        data_dir,
        database_dir,
        database_engine_marker,
        nodekey):
    assert not trinity_config.logfile_path.parent.exists()
    assert not is_data_dir_initialized(trinity_config)


def test_not_initialized_without_logfile_path(
        trinity_config,
        data_dir,
        database_dir,
        database_engine_marker,
        nodekey,
        logfile_dir):
    assert not trinity_config.logfile_path.exists()
    assert not is_data_dir_initialized(trinity_config)


def test_full_initialized_data_dir(
        trinity_config,
        data_dir,
        database_dir,
        database_engine_marker,
        nodekey,
        logfile_dir,
        logfile_path):
    assert is_data_dir_initialized(trinity_config)


NODEKEY = decode_hex('0xd18445cc77139cd8e09110e99c9384f0601bd2dfa5b230cda917df7e56b69949')


def test_full_initialized_data_dir_with_custom_nodekey():
    trinity_config = TrinityConfig(network_id=1, nodekey=NODEKEY)

    trinity_config.data_dir.mkdir(parents=True, exist_ok=True)
    trinity_config.database_dir.mkdir(parents=True, exist_ok=True)
    trinity_config.logfile_path.mkdir(parents=True, exist_ok=True)
    trinity_config.logfile_path.touch()

    with trinity_config.database_engine_marker_path.open('w') as engine_marker_file:
        engine_marker_file.write(trinity_config.db_engine)

    assert trinity_config.nodekey_path is None
    assert trinity_config.nodekey is not None

    assert is_data_dir_initialized(trinity_config)
