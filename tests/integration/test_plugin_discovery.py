import pytest
from trinity.plugins.registry import (
    discover_plugins
)


def test_plugin_discovery():
    if not pytest.config.getoption("--integration"):
        pytest.skip("Not asked to run integration tests")

    # This plugin is external to this code base and installed by tox
    # In order to install it locally run:
    # pip install -e trinity-external-plugins/examples/peer_count_reporter
    from peer_count_reporter_plugin import PeerCountReporterPlugin

    plugins = discover_plugins()
    assert PeerCountReporterPlugin in plugins
