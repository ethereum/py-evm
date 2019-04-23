import asyncio
from argparse import (
    ArgumentParser,
    _SubParsersAction,
)

from p2p.tracking.connection import (
    BaseConnectionTracker,
    NoopConnectionTracker,
)

from trinity._utils.shutdown import (
    exit_with_service_and_endpoint,
)
from trinity.db.orm import get_tracking_database
from trinity.constants import (
    BLACKLIST_EVENTBUS_ENDPOINT,
    TrackingBackend,
)
from trinity.endpoint import (
    TrinityEventBusEndpoint,
)
from trinity.extensibility.plugin import (
    BaseIsolatedPlugin,
)
from trinity.tracking import (
    get_nodedb_path,
    clear_node_db,
)

from .cli import NormalizeTrackingBackend
from .server import BlacklistServer
from .tracker import (
    SQLiteConnectionTracker,
    MemoryConnectionTracker,
)


class BlacklistPlugin(BaseIsolatedPlugin):
    tracker: BaseConnectionTracker

    @property
    def name(self) -> str:
        return "Connection Blacklist Database"

    @property
    def normalized_name(self) -> str:
        return BLACKLIST_EVENTBUS_ENDPOINT

    def configure_parser(self, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        tracking_parser = arg_parser.add_argument_group('enode tracking')
        tracking_parser.add_argument(
            '--enode-tracking-backend',
            help=(
                "Configure whether nodes are tracked and how. (sqlite3: persistent "
                "tracking across runs from an on-disk sqlite3 datase, memory: tracking "
                "only in memory, disabled: no tracking)"
            ),
            action=NormalizeTrackingBackend,
            choices=('sqlite3', 'memory', 'disabled'),
            default=TrackingBackend.sqlite3,
            type=str,
        )

        attach_parser = subparser.add_parser(
            'remove-enode-db',
            help='Remove the on-disk sqlite database that tracks data about node connections',
        )
        attach_parser.set_defaults(func=clear_node_db)

    def on_ready(self, manager_eventbus: TrinityEventBusEndpoint) -> None:
        self.start()

    def _get_tracker(self) -> BaseConnectionTracker:
        config = self.context.trinity_config

        if config.tracking_backend is TrackingBackend.sqlite3:
            session = get_tracking_database(get_nodedb_path(config))
            return SQLiteConnectionTracker(session)
        elif config.tracking_backend is TrackingBackend.memory:
            return MemoryConnectionTracker()
        elif config.tracking_backend is TrackingBackend.disabled:
            return NoopConnectionTracker()
        else:
            raise Exception(f"INVARIANT: {config.tracking_backend}")

    def do_start(self) -> None:
        tracker = self._get_tracker()

        loop = asyncio.get_event_loop()
        blacklist_service = BlacklistServer(
            event_bus=self.event_bus,
            tracker=tracker,
        )
        asyncio.ensure_future(exit_with_service_and_endpoint(blacklist_service, self.event_bus))
        asyncio.ensure_future(blacklist_service.run())
        loop.run_forever()
        loop.close()
