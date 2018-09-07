from argparse import (
    ArgumentParser,
    _SubParsersAction,
)
import asyncio

from cancel_token import (
    CancelToken
)

from eth.chains.base import (
    BaseChain
)

from p2p.peer import (
    PeerPool
)

from trinity.constants import (
    SYNC_LIGHT
)
from trinity.extensibility import (
    BaseEvent,
    BasePlugin,
)
from trinity.extensibility.events import (
    ResourceAvailableEvent
)
from trinity.plugins.builtin.light_peer_chain_bridge.light_peer_chain_bridge import (
    LightPeerChainEventBusBridge
)


class LightPeerChainBridgePlugin(BasePlugin):
    """
    This plugin does some boiler plate magic so that other *isolated* plugins that run in their
    own process can be built.
    It sits in the networking process and listens to certain requests on the eventbus
    to forward them to the `LightPeerChain` to get answers and broadcast the results back to the
    remote caller via eventbus.
    It also provides an `EventBusLightPeerChain` that isolated plugins can use
    to effectively get an identical interface to the `LightPeerChain` that can be used across
    processes.
    """

    chain: BaseChain = None

    @property
    def name(self) -> str:
        return "LightPeerChain Bridge"

    def should_start(self) -> bool:
        return self.chain is not None

    def handle_event(self, activation_event: BaseEvent) -> None:
        if isinstance(activation_event, ResourceAvailableEvent):
            if activation_event.resource_type is BaseChain:
                self.chain = activation_event.resource

    def start(self) -> None:
        self.logger.info('LightPeerChain Bridge started')
        bridge = LightPeerChainEventBusBridge(self.chain._peer_chain, self.context.event_bus)
