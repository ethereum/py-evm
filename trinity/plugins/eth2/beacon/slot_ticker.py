import asyncio
import time

from cancel_token import (
    CancelToken,
)
from dataclasses import (
    dataclass,
)
from lahja import (
    BaseEvent,
    BroadcastConfig,
)

from eth2.beacon.typing import (
    Second,
    Slot,
)
from p2p.service import (
    BaseService,
)
from trinity._utils.shellart import (
    bold_green,
)
from trinity.endpoint import (
    TrinityEventBusEndpoint,
)

DEFAULT_CHECK_FREQUENCY = 6


@dataclass
class SlotTickEvent(BaseEvent):

    slot: Slot
    elapsed_time: Second
    is_second_tick: bool


class SlotTicker(BaseService):
    genesis_slot: Slot
    genesis_time: int
    seconds_per_slot: Second
    latest_slot: Slot
    event_bus: TrinityEventBusEndpoint

    def __init__(
            self,
            genesis_slot: Slot,
            genesis_time: int,
            seconds_per_slot: Second,
            event_bus: TrinityEventBusEndpoint,
            token: CancelToken = None) -> None:
        super().__init__(token)
        self.genesis_slot = genesis_slot
        self.genesis_time = genesis_time
        # FIXME: seconds_per_slot is assumed to be constant here.
        # Should it changed in the future fork, fix it as #491 described.
        self.seconds_per_slot = seconds_per_slot
        self.latest_slot = genesis_slot
        self.event_bus = event_bus

    async def _run(self) -> None:
        self.run_daemon_task(self._keep_ticking())
        await self.cancellation()

    async def _keep_ticking(self) -> None:
        """
        Ticker should tick twice in one slot:
        one for a new slot, one for the second half of an already ticked slot,
        e.g., if `seconds_per_slot` is `6`, for slot `49` it should tick once
        for the first 3 seconds and once for the last 3 seconds.
        """
        # `has_sent_second_half_slot_tick` is used to prevent another tick
        # for the second half of a ticked slot.
        has_sent_second_half_slot_tick = False
        while self.is_operational:
            elapsed_time = Second(int(time.time()) - self.genesis_time)
            if elapsed_time >= self.seconds_per_slot:
                slot = Slot(elapsed_time // self.seconds_per_slot + self.genesis_slot)
                is_second_tick = (
                    (elapsed_time % self.seconds_per_slot) >= (self.seconds_per_slot / 2)
                )
                # Case 1: new slot
                if slot > self.latest_slot:
                    self.logger.debug(
                        bold_green("Tick  this_slot=%s elapsed=%s"),
                        slot,
                        elapsed_time,
                    )
                    self.latest_slot = slot
                    await self.event_bus.broadcast(
                        SlotTickEvent(
                            slot=slot,
                            elapsed_time=elapsed_time,
                            is_second_tick=is_second_tick,
                        ),
                        BroadcastConfig(internal=True),
                    )
                    has_sent_second_half_slot_tick = is_second_tick
                # Case 2: second half of an already ticked slot and it hasn't tick yet
                elif is_second_tick and not has_sent_second_half_slot_tick:
                    self.logger.debug(bold_green("Tick  this_slot=%s (second-tick)"), slot)
                    await self.event_bus.broadcast(
                        SlotTickEvent(
                            slot=slot,
                            elapsed_time=elapsed_time,
                            is_second_tick=is_second_tick,
                        ),
                        BroadcastConfig(internal=True),
                    )
                    has_sent_second_half_slot_tick = True

            await asyncio.sleep(self.seconds_per_slot // DEFAULT_CHECK_FREQUENCY)
