import pytest

from trinity.protocol.common.events import PeerCountRequest

from p2p.tools.paragon import (
    get_directly_linked_peers,
    ParagonMockPeerPoolWithConnectedPeers,
    ParagonPeerPoolEventServer,
)

from tests.core.integration_test_helpers import (
    make_peer_pool_answer_event_bus_requests,
)


@pytest.mark.asyncio
async def test_event_bus_requests_against_peer_pool(request, event_loop, event_bus):

    alice, bob = await get_directly_linked_peers(request, event_loop)
    peer_pool = ParagonMockPeerPoolWithConnectedPeers([alice, bob])
    await make_peer_pool_answer_event_bus_requests(
        event_bus, peer_pool, handler_type=ParagonPeerPoolEventServer)

    res = await event_bus.request(PeerCountRequest())

    assert res.peer_count == 2
