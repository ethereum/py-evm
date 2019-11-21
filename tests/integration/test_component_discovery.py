import pytest
from trinity.components.registry import (
    discover_components
)


def test_component_discovery(request):
    if not request.config.getoption("--integration"):
        pytest.skip("Not asked to run integration tests")

    # This component is external to this code base and installed by tox
    # In order to install it locally run:
    # pip install -e trinity-external-components/examples/peer_count_reporter
    from peer_count_reporter_component import PeerCountReporterComponent

    components = discover_components()
    assert PeerCountReporterComponent in components
