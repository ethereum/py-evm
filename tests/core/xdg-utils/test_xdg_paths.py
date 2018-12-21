from pathlib import Path

import pytest

from trinity.exceptions import (
    AmbigiousFileSystem
)

from trinity._utils.xdg import (
    get_xdg_trinity_root,
    get_xdg_cache_home,
    get_xdg_config_home,
    get_xdg_data_home,
)


# These envs may all exist and we need to ensure to monkeypatch kill them
# for each test run, and then only set the ones that are parameterized
AFFECTED_ENVS = [
    'HOME',
    'XDG_DATA_HOME',
    'XDG_TRINITY_ROOT',
    'XDG_CONFIG_HOME',
    'XDG_CACHE_HOME'
]


def clear_envs(monkeypatch):
    for env in AFFECTED_ENVS:
        monkeypatch.delenv(env, raising=False)


def set_envs(monkeypatch, envs):
    for pair in envs:
        monkeypatch.setenv(pair[0], pair[1])


@pytest.mark.parametrize(
    'envs, resolver, expected',
    (
        # get_xdg_data_home()
        ([('HOME', 'home'), ('XDG_DATA_HOME', 'test')], get_xdg_data_home, 'test'),
        ([('XDG_DATA_HOME', 'test')], get_xdg_data_home, 'test'),
        ([('HOME', 'test')], get_xdg_data_home, 'test/.local/share'),
        ([], get_xdg_data_home, AmbigiousFileSystem),
        # get_xdg_trinity_root()
        ([('HOME', 'home'), ('XDG_TRINITY_ROOT', 'test')], get_xdg_trinity_root, 'test'),
        ([('XDG_TRINITY_ROOT', 'test')], get_xdg_trinity_root, 'test'),
        ([('HOME', 'test')], get_xdg_trinity_root, 'test/.local/share/trinity'),
        ([], get_xdg_trinity_root, AmbigiousFileSystem),
        # get_xdg_config_home()
        ([('HOME', 'home'), ('XDG_CONFIG_HOME', 'test')], get_xdg_config_home, 'test'),
        ([('XDG_CONFIG_HOME', 'test')], get_xdg_config_home, 'test'),
        ([('HOME', 'test')], get_xdg_config_home, 'test/.config'),
        ([], get_xdg_config_home, AmbigiousFileSystem),
        # get_xdg_cache_home()
        ([('HOME', 'home'), ('XDG_CACHE_HOME', 'test')], get_xdg_cache_home, 'test'),
        ([('XDG_CACHE_HOME', 'test')], get_xdg_cache_home, 'test'),
        ([('HOME', 'test')], get_xdg_cache_home, 'test/.cache'),
        ([], get_xdg_cache_home, AmbigiousFileSystem)
    )
)
def test_xdg_path_handling(monkeypatch, envs, resolver, expected):
    clear_envs(monkeypatch)
    set_envs(monkeypatch, envs)

    if expected is AmbigiousFileSystem:
        with pytest.raises(AmbigiousFileSystem):
            resolver()
    else:
        assert resolver() == Path(expected)
