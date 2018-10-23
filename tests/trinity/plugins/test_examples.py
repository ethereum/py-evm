from trinity.plugins.examples import (
    PeerCountReporterPlugin,
)


def test_can_instantiate_examples():
    plugin = PeerCountReporterPlugin()
    assert plugin.name == "Peer Count Reporter"
