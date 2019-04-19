import pytest

import os

from trinity._utils.filesystem import (
    is_under_path,
)
from trinity.initialization import (
    is_data_dir_initialized,
    initialize_data_dir,
)
from trinity.config import (
    TrinityConfig,
)
from trinity.exceptions import (
    MissingPath,
)


@pytest.fixture
def trinity_config():
    return TrinityConfig(network_id=1)


def _manually_add_datadir(trinity_config):
    os.makedirs(trinity_config.data_dir, exist_ok=True)
    assert os.path.exists(trinity_config.data_dir)


def test_initializing_data_dir_from_nothing(trinity_config):
    assert not os.path.exists(trinity_config.data_dir)
    assert not is_data_dir_initialized(trinity_config)

    initialize_data_dir(trinity_config)

    assert is_data_dir_initialized(trinity_config)


def test_initializing_data_dir_from_empty_data_dir(trinity_config):
    _manually_add_datadir(trinity_config)
    assert not is_data_dir_initialized(trinity_config)

    initialize_data_dir(trinity_config)

    assert is_data_dir_initialized(trinity_config)


def test_initializing_data_dir_with_missing_nodekey(trinity_config):
    _manually_add_datadir(trinity_config)
    assert not os.path.exists(trinity_config.nodekey_path)
    assert not is_data_dir_initialized(trinity_config)

    initialize_data_dir(trinity_config)

    assert is_data_dir_initialized(trinity_config)


def test_always_creates_logs_folder_in_default_dir(trinity_config):
    # log dir is in default path, data dir has other data in it, but is missing logs folder
    assert is_under_path(trinity_config.trinity_root_dir, trinity_config.log_dir)
    _manually_add_datadir(trinity_config)
    file_in_data_dir = trinity_config.data_dir / "other_things_present"
    file_in_data_dir.touch()
    assert not trinity_config.log_dir.exists()
    assert not is_data_dir_initialized(trinity_config)

    # should create log dir
    initialize_data_dir(trinity_config)

    assert trinity_config.log_dir.exists()


def test_creates_log_dir_in_non_default_data_dir_with_clean_folder(trinity_config):
    # log dir is not in default path, data dir has no other data/folders in it
    trinity_config.data_dir = trinity_config.trinity_root_dir.parent / "custom-data-dir"
    _manually_add_datadir(trinity_config)
    assert not is_under_path(trinity_config.trinity_root_dir, trinity_config.log_dir)
    assert not is_under_path(trinity_config.trinity_root_dir, trinity_config.data_dir)
    assert is_under_path(trinity_config.data_dir, trinity_config.log_dir)
    assert not any(trinity_config.data_dir.iterdir())
    assert not is_data_dir_initialized(trinity_config)

    # should create log dir
    initialize_data_dir(trinity_config)

    assert trinity_config.log_dir.exists()


def test_ignore_log_dir_in_non_default_data_dir_with_dirty_folder(trinity_config):
    # log dir is not in default path, data dir has other data in it, and is missing logs folder
    trinity_config.data_dir = trinity_config.trinity_root_dir.parent / "custom-data-dir"
    _manually_add_datadir(trinity_config)
    assert not is_under_path(trinity_config.trinity_root_dir, trinity_config.log_dir)
    assert is_under_path(trinity_config.data_dir, trinity_config.log_dir)
    file_in_data_dir = trinity_config.data_dir / "other_things_present"
    file_in_data_dir.touch()
    assert not trinity_config.log_dir.exists()
    assert not is_data_dir_initialized(trinity_config)

    # should *not* create log dir
    with pytest.raises(MissingPath, match="logging"):
        initialize_data_dir(trinity_config)

    assert not trinity_config.log_dir.exists()
