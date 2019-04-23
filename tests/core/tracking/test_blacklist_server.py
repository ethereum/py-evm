import asyncio
import pytest

from lahja import BroadcastConfig

from p2p.tools.factories import NodeFactory

from trinity.constants import (
    NETWORKING_EVENTBUS_ENDPOINT,
)
from trinity.plugins.builtin.blacklist.server import BlacklistServer
from trinity.plugins.builtin.blacklist.tracker import (
    EventBusConnectionTracker,
    MemoryConnectionTracker,
)


@pytest.mark.asyncio
async def test_blacklist_server_and_event_bus_tracker(event_loop, event_bus):
    tracker = MemoryConnectionTracker()
    remote_a = NodeFactory()
    tracker.record_blacklist(remote_a, 60, "testing")

    assert tracker.should_connect_to(remote_a) is False

    service = BlacklistServer(event_bus, tracker)

    # start the server
    asyncio.ensure_future(service.run(), loop=event_loop)
    await service.events.started.wait()

    config = BroadcastConfig(filter_endpoint=NETWORKING_EVENTBUS_ENDPOINT)
    bus_tracker = EventBusConnectionTracker(event_bus, config=config)

    # ensure we can read fromt he tracker over the event bus
    assert await bus_tracker.coro_should_connect_to(remote_a) is False

    # ensure we can write to the tracker over the event bus
    remote_b = NodeFactory()

    assert await bus_tracker.coro_should_connect_to(remote_b) is True

    bus_tracker.record_blacklist(remote_b, 60, "testing")

    assert await bus_tracker.coro_should_connect_to(remote_b) is False
    assert tracker.should_connect_to(remote_b) is False
