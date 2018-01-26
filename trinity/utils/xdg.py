import os

from .filesystem import (
    is_under_path,
)


XDG_CACHE_HOME = os.environ.get(
    'XDG_CACHE_HOME',
    os.path.expandvars(os.path.join('$HOME', '.cache'))
)

XDG_CONFIG_HOME = os.environ.get(
    'XDG_CONFIG_HOME',
    os.path.expandvars(os.path.join('$HOME', '.config')),
)

XDG_DATA_HOME = os.environ.get(
    'XDG_DATA_HOME',
    os.path.expandvars(os.path.join('$HOME', '.local', 'share')),
)


def get_xdg_trinity_home():
    """
    Returns the base directory under which trinity will store all data.
    """
    return os.environ.get(
        'TRINITY_HOME',
        os.path.join(XDG_DATA_HOME, 'trinity'),
    )


def is_under_xdg_trinity_home(path):
    return is_under_path(
        get_xdg_trinity_home(),
        path,
    )
