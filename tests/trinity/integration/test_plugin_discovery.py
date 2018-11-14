from trinity.plugins.registry import (
    get_all_plugins
)
# This plugin is external to this code base and installed by tox
# In order to install it locally run:
# pip install -e trinity-external-plugins/examples/peer_count_reporter
from peer_count_reporter_plugin import PeerCountReporterPlugin


def test_plugin_discovery():
    plugins = [type(plugin) for plugin in get_all_plugins()]
    assert PeerCountReporterPlugin in plugins
