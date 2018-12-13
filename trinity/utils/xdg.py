import os

from pathlib import Path

from trinity.exceptions import (
    AmbigiousFileSystem
)


def get_home() -> Path:
    try:
        return Path(os.environ['HOME'])
    except KeyError:
        raise AmbigiousFileSystem('$HOME environment variable not set')


def get_xdg_cache_home() -> Path:
    try:
        return Path(os.environ['XDG_CACHE_HOME'])
    except KeyError:
        return get_home() / '.cache'


def get_xdg_config_home() -> Path:
    try:
        return Path(os.environ['XDG_CONFIG_HOME'])
    except KeyError:
        return get_home() / '.config'


def get_xdg_data_home() -> Path:
    try:
        return Path(os.environ['XDG_DATA_HOME'])
    except KeyError:
        return get_home() / '.local' / 'share'


def get_xdg_trinity_root(app_name: str) -> Path:
    """
    Returns the base directory under which trinity will store all data.
    """
    xdg_lookup_key = f'XDG_{app_name.upper()}_ROOT'
    try:
        return Path(os.environ[xdg_lookup_key])
    except KeyError:
        return get_xdg_data_home() / app_name
