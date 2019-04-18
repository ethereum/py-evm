import pytest

import os

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
    os.makedirs(trinity_config.data_dir, exist_ok=True)
    assert os.path.exists(trinity_config.data_dir)
    return trinity_config.data_dir


def test_initializing_data_dir_from_nothing(trinity_config):
    assert not os.path.exists(trinity_config.data_dir)
    assert not is_data_dir_initialized(trinity_config)

    initialize_data_dir(trinity_config)

    assert is_data_dir_initialized(trinity_config)


def test_initializing_data_dir_from_empty_data_dir(trinity_config, data_dir):
    assert not is_data_dir_initialized(trinity_config)

    initialize_data_dir(trinity_config)

    assert is_data_dir_initialized(trinity_config)


def test_initializing_data_dir_with_missing_nodekey(trinity_config, data_dir):
    assert not os.path.exists(trinity_config.nodekey_path)
    assert not is_data_dir_initialized(trinity_config)

    initialize_data_dir(trinity_config)

    assert is_data_dir_initialized(trinity_config)
