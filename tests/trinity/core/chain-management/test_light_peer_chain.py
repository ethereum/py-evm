from trinity.sync.light.service import (
    LightPeerChain
)
from trinity.plugins.builtin.light_peer_chain_bridge import (
    EventBusLightPeerChain,
)


# These tests may seem obvious but they safe us from runtime errors where
# changes are made to the `BaseLightPeerChain` that are then forgotton to
# implement on both derived chains.

def test_can_instantiate_eventbus_light_peer_chain():
    chain = EventBusLightPeerChain(None)
    assert chain is not None


def test_can_instantiate_light_peer_chain():
    chain = LightPeerChain(None, None)
    assert chain is not None
