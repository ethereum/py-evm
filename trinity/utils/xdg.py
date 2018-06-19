import os

from pathlib import Path

from trinity.exceptions import (
    AmbigiousFileSystem
)

from .filesystem import (
    is_under_path,
)


def get_home() -> str:
    try:
        return os.environ['HOME']
    except KeyError:
        raise AmbigiousFileSystem('$HOME environment variable not set')


def get_xdg_cache_home() -> str:
    try:
        return os.environ['XDG_CACHE_HOME']
    except KeyError:
        return os.path.join(get_home(), '.cache')


def get_xdg_config_home() -> str:
    try:
        return os.environ['XDG_CONFIG_HOME']
    except KeyError:
        return os.path.join(get_home(), '.config')


def get_xdg_data_home() -> str:
    try:
        return os.environ['XDG_DATA_HOME']
    except KeyError:
        return os.path.join(get_home(), '.local', 'share')


def get_xdg_trinity_root() -> str:
    """
    Returns the base directory under which trinity will store all data.
    """
    try:
        return os.environ['XDG_TRINITY_ROOT']
    except KeyError:
        return os.path.join(get_xdg_data_home(), 'trinity')


def is_under_xdg_trinity_root(path: Path) -> bool:
    return is_under_path(
        get_xdg_trinity_root(),
        str(path),
    )
