import pytest

from trinity.exceptions import (
    AmbigiousFileSystem
)

from trinity.utils.xdg import (
    get_xdg_trinity_root,
    get_xdg_cache_home,
    get_xdg_config_home,
    get_xdg_data_home,
)


def test_data_home_discovery(monkeypatch):

    # Only XDG_DATA_HOME is set but HOME isn't
    monkeypatch.setenv('XDG_DATA_HOME', 'test')
    monkeypatch.delenv('HOME')

    assert get_xdg_data_home() == 'test'

    # Only HOME is set
    monkeypatch.delenv('XDG_DATA_HOME')
    monkeypatch.setenv('HOME', 'test2')

    assert get_xdg_data_home() == 'test2/.local/share'

    # Nothing is set
    monkeypatch.delenv('HOME')

    with pytest.raises(AmbigiousFileSystem):
        get_xdg_data_home()


def test_trinity_root_discovery(monkeypatch):

    # Only XDG_TRINITY_ROOT is set but HOME isn't
    monkeypatch.setenv('XDG_TRINITY_ROOT', 'test')
    monkeypatch.delenv('HOME')

    assert get_xdg_trinity_root() == 'test'

    # Only HOME is set
    monkeypatch.delenv('XDG_TRINITY_ROOT')
    monkeypatch.setenv('HOME', 'test2')

    assert get_xdg_trinity_root() == 'test2/.local/share/trinity'

    # Nothing is set
    monkeypatch.delenv('HOME')

    with pytest.raises(AmbigiousFileSystem):
        get_xdg_trinity_root()


def test_config_home_discovery(monkeypatch):

    # Only XDG_CONFIG_HOME is set but HOME isn't
    monkeypatch.setenv('XDG_CONFIG_HOME', 'test')
    monkeypatch.delenv('HOME')

    assert get_xdg_config_home() == 'test'

    # Only HOME is set
    monkeypatch.delenv('XDG_CONFIG_HOME')
    monkeypatch.setenv('HOME', 'test2')

    assert get_xdg_config_home() == 'test2/.config'

    # Nothing is set
    monkeypatch.delenv('HOME')

    with pytest.raises(AmbigiousFileSystem):
        get_xdg_config_home()


def test_cache_home_discovery(monkeypatch):

    # Only XDG_CACHE_HOME is set but HOME isn't
    monkeypatch.setenv('XDG_CACHE_HOME', 'test')
    monkeypatch.delenv('HOME')

    assert get_xdg_cache_home() == 'test'

    # Only HOME is set
    monkeypatch.delenv('XDG_CACHE_HOME')
    monkeypatch.setenv('HOME', 'test2')

    assert get_xdg_cache_home() == 'test2/.cache'

    # Nothing is set
    monkeypatch.delenv('HOME')

    with pytest.raises(AmbigiousFileSystem):
        get_xdg_cache_home()
