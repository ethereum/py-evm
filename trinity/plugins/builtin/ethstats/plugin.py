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
    TrinityStartupEvent,
)

from trinity.plugins.builtin.ethstats.ethstats_service import (
    EthstatsService,
)


class EthstatsPlugin(BasePlugin):

    def __init__(self) -> None:
        self.is_enabled: bool = False
        # TODO: make server/secret configurable
        self.service: EthstatsService = EthstatsService('ws://localhost:3000/api', 'SECRET')

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

    def should_start(self) -> bool:
        return self.is_enabled

    def start(self, context: PluginContext) -> None:
        asyncio.ensure_future(self.service.run())
