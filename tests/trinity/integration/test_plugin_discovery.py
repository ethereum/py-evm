from trinity.plugins.registry import (
    discover_plugins
)
# This plugin is external to this code base and installed by tox
# In order to install it locally run:
# pip install -e trinity-external-plugins/examples/peer_count_reporter
try:
    from peer_count_reporter_plugin import PeerCountReporterPlugin
except ImportError:
    # test will fail at runtime, should not fail at import/collection time
    pass


def test_plugin_discovery():
    plugins = [type(plugin) for plugin in discover_plugins()]
    assert PeerCountReporterPlugin in plugins
