import asyncio
import time

from cancel_token import (
    CancelToken,
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


class NewSlotEvent(BaseEvent):
    def __init__(self, slot: Slot, elapsed_time: Second, is_second_signal: bool):
        self.slot = slot
        self.elapsed_time = elapsed_time
        self.is_second_signal = is_second_signal


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
        is_second_signal_sent = False
        while self.is_operational:
            elapsed_time = Second(int(time.time()) - self.genesis_time)
            if elapsed_time >= self.seconds_per_slot:
                slot = Slot(elapsed_time // self.seconds_per_slot + self.genesis_slot)
                is_second_half = (elapsed_time % self.seconds_per_slot) >= self.seconds_per_slot / 2
                if slot > self.latest_slot:
                    self.logger.debug(
                        bold_green(f"New slot: {slot}\tElapsed time: {elapsed_time}")
                    )
                    self.latest_slot = slot
                    is_second_signal = False
                    await self.event_bus.broadcast(
                        NewSlotEvent(
                            slot=slot,
                            elapsed_time=elapsed_time,
                            is_second_signal=is_second_signal,
                        ),
                        BroadcastConfig(internal=True),
                    )
                    is_second_signal_sent = False
                elif slot == self.latest_slot and is_second_half and not is_second_signal_sent:
                    self.logger.debug(
                        bold_green(f"Second half of slot: {slot}")
                    )
                    is_second_signal = True
                    await self.event_bus.broadcast(
                        NewSlotEvent(
                            slot=slot,
                            elapsed_time=elapsed_time,
                            is_second_signal=is_second_signal,
                        ),
                        BroadcastConfig(internal=True),
                    )
                    is_second_signal_sent = True

            await asyncio.sleep(self.seconds_per_slot // DEFAULT_CHECK_FREQUENCY)
