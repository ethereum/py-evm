def test_plugin_discovery():
    from trinity_test_plugin import TestPlugin
    from trinity.plugins.registry import ALL_PLUGINS
    assert any(isinstance(plugin, TestPlugin) for plugin in ALL_PLUGINS)
