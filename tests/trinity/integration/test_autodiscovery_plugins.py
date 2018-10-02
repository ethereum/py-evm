import pytest
from subprocess import call


@pytest.yield_fixture(scope="function")
def manage_plugin_install(event_loop):
    path_plugin = 'tests/trinity/integration/trinity_test_plugin/'
    call(['pip', 'install', path_plugin])
    yield
    call(['pip', 'uninstall', '-y', 'trinity_test_plugin'])


def test_autodiscovery_plugins(manage_plugin_install):
    from trinity_test_plugin import TestPlugin
    from trinity.plugins.registry import ALL_PLUGINS
    assert TestPlugin in ALL_PLUGINS
