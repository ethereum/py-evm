import pytest


@pytest.fixture(autouse=True)
def xdg_trinity_home(monkeypatch, tmpdir):
    """
    Ensure proper test isolation as well as protecting the real directories.
    """
    dir_path = tmpdir.mkdir('xdg_trinity_home')
    monkeypatch.setenv('XDG_TRINITY_HOME', str(dir_path))
    return str(dir_path)
