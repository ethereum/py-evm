import asyncio

import pytest

import time

from trinity.components.eth2.beacon.slot_ticker import (
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
    try:
        slot_tick_event = await asyncio.wait_for(
            event_bus.wait_for(SlotTickEvent),
            timeout=2,
            loop=event_loop,
        )
    except asyncio.TimeoutError:
        raise AssertionError("Slot not ticking")
    assert slot_tick_event.slot > 0
    await slot_ticker.cancel()


@pytest.mark.slow
@pytest.mark.asyncio
async def test_slot_ticker_all_ticks(event_bus, event_loop):
    seconds_per_slot = 3
    slot_ticker = SlotTicker(
        genesis_slot=0,
        genesis_time=int(time.time()) + seconds_per_slot,
        seconds_per_slot=seconds_per_slot,
        event_bus=event_bus,
    )
    asyncio.ensure_future(slot_ticker.run(), loop=event_loop)
    try:
        first_slot_event = await asyncio.wait_for(
            event_bus.wait_for(SlotTickEvent),
            timeout=seconds_per_slot,
            loop=event_loop,
        )
    except asyncio.TimeoutError:
        raise AssertionError("Slot not ticking")
    assert first_slot_event.tick_type.is_start

    try:
        second_slot_event = await asyncio.wait_for(
            event_bus.wait_for(SlotTickEvent),
            timeout=seconds_per_slot,
            loop=event_loop,
        )
    except asyncio.TimeoutError:
        raise AssertionError("Should have gotten the second tick")
    assert second_slot_event.slot == first_slot_event.slot
    assert second_slot_event.tick_type.is_one_third

    try:
        third_slot_event = await asyncio.wait_for(
            event_bus.wait_for(SlotTickEvent),
            timeout=seconds_per_slot,
            loop=event_loop,
        )
    except asyncio.TimeoutError:
        raise AssertionError("Should have gotten the third tick")
    assert third_slot_event.slot == first_slot_event.slot
    assert third_slot_event.tick_type.is_two_third

    await slot_ticker.cancel()
