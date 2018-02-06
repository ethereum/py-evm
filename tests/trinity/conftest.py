import pytest

from trinity.utils.xdg import (
    XDG_DATA_HOME,
    get_xdg_trinity_root,
)
from trinity.utils.filesystem import (
    is_under_path,
)


@pytest.fixture(autouse=True)
def xdg_trinity_root(monkeypatch, tmpdir):
    """
    Ensure proper test isolation as well as protecting the real directories.
    """
    dir_path = tmpdir.mkdir('xdg_trinity_root')
    monkeypatch.setenv('XDG_TRINITY_ROOT', str(dir_path))

    assert not is_under_path(XDG_DATA_HOME, get_xdg_trinity_root())

    return str(dir_path)
