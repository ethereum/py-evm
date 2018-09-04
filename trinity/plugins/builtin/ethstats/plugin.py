import asyncio

from argparse import (
    ArgumentParser,
    _SubParsersAction,
)

from trinity.extensibility import (
    BaseEvent,
    BasePlugin,
    PluginContext,
)
from trinity.extensibility.events import (
    ResourceAvailableEvent,
    TrinityStartupEvent,
)
from eth.chains.base import (
    BaseChain
)
from p2p.peer import (
    PeerPool
)

from trinity.plugins.builtin.ethstats.ethstats_service import (
    EthstatsService,
)


class EthstatsPlugin(BasePlugin):

    def __init__(self) -> None:
        self.is_enabled: bool = False

        self.chain: BaseChain = None
        self.peer_pool: PeerPool = None

    @property
    def name(self) -> str:
        return "Ethstats"

    def configure_parser(self, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        arg_parser.add_argument(
            "--ethstats",
            action="store_true",
            help="Enable node status reporting service (experimental)",
        )

    def handle_event(self, activation_event: BaseEvent) -> None:
        if isinstance(activation_event, TrinityStartupEvent):
            self.is_enabled = activation_event.args.ethstats
        if isinstance(activation_event, ResourceAvailableEvent):
            if activation_event.resource_type is PeerPool:
                self.peer_pool = activation_event.resource
            elif activation_event.resource_type is BaseChain:
                self.chain = activation_event.resource

    def should_start(self) -> bool:
        return all((self.is_enabled, self.chain is not None, self.peer_pool is not None))

    def start(self) -> None:
        service = EthstatsService('ws://localhost:3000/api', 'SECRET', self.chain, self.peer_pool)

        asyncio.ensure_future(service.run())
