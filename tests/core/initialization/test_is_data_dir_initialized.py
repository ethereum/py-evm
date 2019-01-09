import os
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
    os.makedirs(trinity_config.data_dir, exist_ok=True)
    assert os.path.exists(trinity_config.data_dir)
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
def ipc_dir(trinity_config):
    os.makedirs(trinity_config.ipc_dir, exist_ok=True)
    assert os.path.exists(trinity_config.ipc_dir)
    return trinity_config.ipc_dir


@pytest.fixture
def pid_dir(trinity_config):
    os.makedirs(trinity_config.pid_dir, exist_ok=True)
    assert os.path.exists(trinity_config.pid_dir)
    return trinity_config.ipc_dir


@pytest.fixture
def nodekey(trinity_config, data_dir):
    with open(trinity_config.nodekey_path, 'wb') as nodekey_file:
        nodekey_file.write(b'\x01' * 32)
    return trinity_config.nodekey_path


def test_not_initialized_without_data_dir(trinity_config):
    assert not os.path.exists(trinity_config.data_dir)
    assert not is_data_dir_initialized(trinity_config)


def test_not_initialized_without_nodekey_file(trinity_config, data_dir):
    assert not os.path.exists(trinity_config.nodekey_path)
    assert not is_data_dir_initialized(trinity_config)


def test_not_initialized_without_logfile_dir(trinity_config, data_dir, nodekey):
    assert not os.path.exists(trinity_config.logfile_path.parent)
    assert not is_data_dir_initialized(trinity_config)


def test_not_initialized_without_logfile_path(
        trinity_config,
        data_dir,
        nodekey,
        logfile_dir):
    assert not os.path.exists(trinity_config.logfile_path)
    assert not is_data_dir_initialized(trinity_config)


def test_not_initialized_without_ipc_dir(
        trinity_config,
        data_dir,
        nodekey,
        logfile_dir,
        logfile_path):
    assert not os.path.exists(trinity_config.ipc_dir)
    assert not is_data_dir_initialized(trinity_config)


def test_not_initialized_without_pid_dir(
        trinity_config,
        data_dir,
        nodekey,
        logfile_dir,
        logfile_path,
        ipc_dir):
    assert not os.path.exists(trinity_config.pid_dir)
    assert not is_data_dir_initialized(trinity_config)


def test_full_initialized_data_dir(
        trinity_config,
        data_dir,
        nodekey,
        logfile_dir,
        logfile_path,
        ipc_dir,
        pid_dir):
    assert is_data_dir_initialized(trinity_config)


NODEKEY = decode_hex('0xd18445cc77139cd8e09110e99c9384f0601bd2dfa5b230cda917df7e56b69949')


def test_full_initialized_data_dir_with_custom_nodekey():
    trinity_config = TrinityConfig(network_id=1, nodekey=NODEKEY)

    os.makedirs(trinity_config.data_dir, exist_ok=True)
    os.makedirs(trinity_config.logfile_path, exist_ok=True)
    os.makedirs(trinity_config.ipc_dir, exist_ok=True)
    os.makedirs(trinity_config.pid_dir, exist_ok=True)
    trinity_config.logfile_path.touch()

    assert trinity_config.nodekey_path is None
    assert trinity_config.nodekey is not None

    assert is_data_dir_initialized(trinity_config)
