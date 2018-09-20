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
from trinity.extensibility import (
    BaseEvent,
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

    def should_start(self) -> bool:
        return self.chain is not None and self.context.chain_config.sync_mode == SYNC_LIGHT

    def handle_event(self, activation_event: BaseEvent) -> None:
        if isinstance(activation_event, ResourceAvailableEvent):
            if activation_event.resource_type is BaseChain:
                self.chain = activation_event.resource

    def start(self) -> None:
        self.logger.info('LightPeerChain Bridge started')
        chain = cast(LightDispatchChain, self.chain)
        self.handler = LightPeerChainEventBusHandler(chain._peer_chain, self.context.event_bus)
        asyncio.ensure_future(self.handler.run())

    async def stop(self) -> None:
        # This isn't really needed for the standard shutdown case as the LightPeerChain will
        # automatically shutdown whenever the `CancelToken` it was chained with is triggered.
        # It may still be useful to stop the LightPeerChain Bridge plugin individually though.
        if self.handler.is_operational:
            await self.handler.cancel()
            self.logger.info("Successfully stopped LightPeerChain Bridge")
