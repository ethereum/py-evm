import asyncio
from typing import (
    cast
)

from eth.chains.base import (
    BaseChain
)

from trinity.constants import (
    SYNC_LIGHT
)
from trinity.endpoint import (
    TrinityEventBusEndpoint,
)
from trinity.extensibility import (
    BaseAsyncStopPlugin,
)
from trinity.chains.light import (
    LightDispatchChain,
)
from trinity.extensibility.events import (
    ResourceAvailableEvent
)
from trinity.plugins.builtin.light_peer_chain_bridge import (
    LightPeerChainEventBusHandler
)


class LightPeerChainBridgePlugin(BaseAsyncStopPlugin):
    """
    The ``LightPeerChainBridgePlugin`` runs in the ``networking`` process and acts as a bridge
    between other processes and the ``LightPeerChain``.
    It runs only in ``light`` mode.
    Other plugins can instantiate the ``EventBusLightPeerChain`` from separate processes to
    interact with the ``LightPeerChain`` indirectly.
    """

    chain: BaseChain = None
    handler: LightPeerChainEventBusHandler = None

    @property
    def name(self) -> str:
        return "LightPeerChain Bridge"

    def on_ready(self, manager_eventbus: TrinityEventBusEndpoint) -> None:
        if self.boot_info.args.sync_mode != SYNC_LIGHT:
            return

        self.event_bus.subscribe(
            ResourceAvailableEvent,
            self.handle_event
        )

    def handle_event(self, event: ResourceAvailableEvent) -> None:
        if event.resource_type is BaseChain:
            self.chain = event.resource
            self.start()

    def do_start(self) -> None:
        chain = cast(LightDispatchChain, self.chain)
        self.handler = LightPeerChainEventBusHandler(chain._peer_chain, self.event_bus)
        asyncio.ensure_future(self.handler.run())

    async def do_stop(self) -> None:
        # This isn't really needed for the standard shutdown case as the LightPeerChain will
        # automatically shutdown whenever the `CancelToken` it was chained with is triggered.
        # It may still be useful to stop the LightPeerChain Bridge plugin individually though.
        if self.handler.is_operational:
            await self.handler.cancel()
            self.logger.info("Successfully stopped LightPeerChain Bridge")
