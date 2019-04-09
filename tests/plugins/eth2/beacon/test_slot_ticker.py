import pytest
from trinity.plugins.eth2.beacon.slot_ticker import (
    SlotTicker,
    NewSlotEvent,
)
import asyncio


@pytest.mark.asyncio
async def test_slot_ticker_ticking(event_bus, event_loop):
    slot_ticker = SlotTicker(
        genesis_slot=0,
        genesis_time=0,
        chain=None,
        event_bus=event_bus,
    )

    def get_seconds_per_slot():
        return 1

    # mock get_seconds_per_slot
    slot_ticker.get_seconds_per_slot = get_seconds_per_slot

    asyncio.ensure_future(slot_ticker.run(), loop=event_loop)
    await slot_ticker.events.started.wait()
    try:
        new_slot_event = await asyncio.wait_for(
            event_bus.wait_for(NewSlotEvent),
            timeout=2,
            loop=event_loop,
        )
    except asyncio.TimeoutError:
        assert False, "Slot not ticking"
    assert new_slot_event.slot > 0
    await slot_ticker.cancel()
