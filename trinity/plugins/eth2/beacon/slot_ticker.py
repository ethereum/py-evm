import asyncio
import time
from eth2.beacon.typing import (
    Slot,
    Second,
)
from trinity.endpoint import TrinityEventBusEndpoint

from eth2.beacon.chains.base import (
    BaseBeaconChain,
)
from trinity._utils.shellart import (
    bold_green,
)
from lahja import (
    BaseEvent,
    BroadcastConfig,
)

from p2p.service import BaseService

from cancel_token import (
    CancelToken,
)

DEFAULT_CHECK_FREQUENCY = 5


class NewSlotEvent(BaseEvent):
    def __init__(self, slot: Slot, elapsed_time: Second):
        self.slot = slot
        self.elapsed_time = elapsed_time


class SlotTicker(BaseService):

    def __init__(
            self,
            genesis_slot: Slot,
            genesis_time: int,
            chain: BaseBeaconChain,
            event_bus: TrinityEventBusEndpoint,
            token: CancelToken = None) -> None:
        super().__init__(token)
        self.genesis_slot = genesis_slot
        self.genesis_time = genesis_time
        self.chain = chain
        self.latest_slot = Slot(0)
        self.event_bus = event_bus

    async def _run(self) -> None:
        self.run_daemon_task(self._keep_ticking())
        await self.cancellation()

    def get_seconds_per_slot(self) -> Second:
        state_machine = self.chain.get_state_machine()
        return state_machine.config.SECONDS_PER_SLOT

    async def _keep_ticking(self) -> None:
        while self.is_operational:
            seconds_per_slot = self.get_seconds_per_slot()
            elapsed_time = Second(int(time.time()) - self.genesis_time)
            if elapsed_time >= seconds_per_slot:
                slot = Slot(elapsed_time // seconds_per_slot + self.genesis_slot)
                if slot > self.latest_slot:
                    self.logger.debug(
                        bold_green(f"New slot: {slot}\tElapsed time: {elapsed_time}")
                    )
                    self.latest_slot = slot
                    self.event_bus.broadcast(
                        NewSlotEvent(
                            slot=slot,
                            elapsed_time=elapsed_time,
                        ),
                        BroadcastConfig(internal=True),
                    )
            await asyncio.sleep(seconds_per_slot // DEFAULT_CHECK_FREQUENCY)
