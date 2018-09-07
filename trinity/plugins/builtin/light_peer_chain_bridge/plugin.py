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
    BasePlugin,
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


class LightPeerChainBridgePlugin(BasePlugin):
    """
    The ``LightPeerChainBridgePlugin`` runs in the ``networking`` process and acts as a bridge
    between other processes and the ``LightPeerChain``.
    It runs only in ``light`` mode.
    Other plugins can instantiate the ``EventBusLightPeerChain`` from separate processes to
    interact with the ``LightPeerChain`` indirectly.
    """

    chain: BaseChain = None

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
        handler = LightPeerChainEventBusHandler(chain._peer_chain, self.context.event_bus)
        asyncio.ensure_future(handler.run())
