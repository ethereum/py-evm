import pytest

from trinity.protocol.common.events import PeerCountRequest

from p2p.tools.paragon import (
    ParagonMockPeerPoolWithConnectedPeers,
)
from p2p.tools.factories import (
    ParagonPeerPairFactory,
)

from tests.core.integration_test_helpers import (
    run_peer_pool_event_server,
)


@pytest.mark.asyncio
async def test_event_bus_requests_against_peer_pool(request, event_loop, event_bus):
    async with ParagonPeerPairFactory() as (alice, bob):
        peer_pool = ParagonMockPeerPoolWithConnectedPeers([alice, bob])
        async with run_peer_pool_event_server(event_bus, peer_pool):

            await event_bus.wait_until_any_endpoint_subscribed_to(PeerCountRequest)

            res = await event_bus.request(PeerCountRequest())

            assert res.peer_count == 2
