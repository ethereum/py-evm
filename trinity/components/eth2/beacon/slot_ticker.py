import asyncio
import time
from typing import Optional, Set

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

from lahja import EndpointAPI

from eth2.beacon.typing import (
    Second,
    Slot,
)
from p2p.service import (
    BaseService,
)
from trinity._utils.shellart import (
    bold_white,
)
from trinity.components.eth2.misc.tick_type import TickType


@dataclass
class SlotTickEvent(BaseEvent):

    slot: Slot
    elapsed_time: Second
    tick_type: TickType


class SlotTicker(BaseService):
    genesis_slot: Slot
    genesis_time: int
    seconds_per_slot: Second
    latest_slot: Slot
    event_bus: EndpointAPI

    def __init__(
            self,
            genesis_slot: Slot,
            genesis_time: int,
            seconds_per_slot: Second,
            event_bus: EndpointAPI,
            check_frequency: Optional[int] = None,
            token: CancelToken = None) -> None:
        super().__init__(token)
        self.genesis_slot = genesis_slot
        self.genesis_time = genesis_time
        # FIXME: seconds_per_slot is assumed to be constant here.
        # Should it changed in the future fork, fix it as #491 described.
        self.seconds_per_slot = seconds_per_slot
        # Check twice per second by default
        self.check_frequency = seconds_per_slot * 2 if check_frequency is None else check_frequency
        self.latest_slot = genesis_slot
        self.event_bus = event_bus

    async def _run(self) -> None:
        self.run_daemon_task(self._keep_ticking())
        await self.cancellation()

    async def _keep_ticking(self) -> None:
        """
        Ticker should tick three times in one slot:
        SLOT_START: at the beginning of the slot
        SLOT_ONE_THIRD: at 1/3 of the slot
        SLOT_TWO_THIRD: at 2/3 of the slot
        """
        # Use `sent_tick_types_at_slot` set to record
        # the tick types that haven been sent at current slot.
        sent_tick_types_at_slot: Set[TickType] = set()
        while self.is_operational:
            elapsed_time = Second(int(time.time()) - self.genesis_time)

            # Skip genesis slot
            if elapsed_time < self.seconds_per_slot:
                continue

            elapsed_slots = elapsed_time // self.seconds_per_slot
            slot = Slot(elapsed_slots + self.genesis_slot)
            tick_type = self._get_tick_type(elapsed_time)

            # New slot
            if slot > self.latest_slot:
                self.latest_slot = slot
                await self._broadcast_slot_tick_event(slot, elapsed_time, tick_type)
                # Clear set
                sent_tick_types_at_slot = set()
                sent_tick_types_at_slot.add(TickType.SLOT_START)
            elif (
                not tick_type.is_start and tick_type not in sent_tick_types_at_slot
            ):
                await self._broadcast_slot_tick_event(slot, elapsed_time, tick_type)
                sent_tick_types_at_slot.add(tick_type)

            await asyncio.sleep(self.seconds_per_slot // self.check_frequency)

    async def _broadcast_slot_tick_event(
        self, slot: Slot, elapsed_time: Second, tick_type: TickType
    ) -> None:
        self.logger.debug(
            bold_white("[%s] tick at %ss of slot #%s, total elapsed %ds"),
            tick_type, elapsed_time % self.seconds_per_slot, slot, elapsed_time,
        )
        await self.event_bus.broadcast(
            SlotTickEvent(
                slot=slot,
                elapsed_time=elapsed_time,
                tick_type=tick_type,
            ),
            BroadcastConfig(internal=True),
        )

    def _get_tick_type(self, elapsed_time: Second) -> TickType:
        elapsed_time_in_slot = elapsed_time % self.seconds_per_slot
        if elapsed_time_in_slot >= (self.seconds_per_slot * 2 / 3):
            tick_type = TickType.SLOT_TWO_THIRD
        elif elapsed_time_in_slot >= (self.seconds_per_slot / 3):
            tick_type = TickType.SLOT_ONE_THIRD
        else:
            tick_type = TickType.SLOT_START
        return tick_type
