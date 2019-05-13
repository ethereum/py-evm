import asyncio

import pytest

import time

from trinity.plugins.eth2.beacon.slot_ticker import (
    SlotTickEvent,
    SlotTicker,
)


@pytest.mark.asyncio
async def test_slot_ticker_ticking(event_bus, event_loop):
    slot_ticker = SlotTicker(
        genesis_slot=0,
        genesis_time=int(time.time()) + 1,
        seconds_per_slot=1,
        event_bus=event_bus,
    )
    asyncio.ensure_future(slot_ticker.run(), loop=event_loop)
    await slot_ticker.events.started.wait()
    try:
        slot_tick_event = await asyncio.wait_for(
            event_bus.wait_for(SlotTickEvent),
            timeout=2,
            loop=event_loop,
        )
    except asyncio.TimeoutError:
        assert False, "Slot not ticking"
    assert slot_tick_event.slot > 0
    await slot_ticker.cancel()


@pytest.mark.asyncio
async def test_slot_ticker_second_half_tick(event_bus, event_loop):
    slot_ticker = SlotTicker(
        genesis_slot=0,
        genesis_time=int(time.time()) + 1,
        seconds_per_slot=2,
        event_bus=event_bus,
    )
    asyncio.ensure_future(slot_ticker.run(), loop=event_loop)
    await slot_ticker.events.started.wait()
    try:
        first_slot_event = await asyncio.wait_for(
            event_bus.wait_for(SlotTickEvent),
            timeout=4,
            loop=event_loop,
        )
    except asyncio.TimeoutError:
        assert False, "Slot not ticking"
    assert not first_slot_event.is_second_tick
    try:
        second_slot_event = await asyncio.wait_for(
            event_bus.wait_for(SlotTickEvent),
            timeout=4,
            loop=event_loop,
        )
    except asyncio.TimeoutError:
        assert False, "No second half tick"
    assert second_slot_event.slot == first_slot_event.slot
    assert second_slot_event.is_second_tick
    await slot_ticker.cancel()
