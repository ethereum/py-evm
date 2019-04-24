import asyncio

from p2p.tracking.connection import (
    BaseConnectionTracker,
    NoopConnectionTracker,
)

from trinity._utils.shutdown import (
    exit_with_service_and_endpoint,
)
from trinity.db.orm import get_tracking_database
from trinity.db.network import get_networkdb_path
from trinity.constants import (
    BLACKLIST_EVENTBUS_ENDPOINT,
)
from trinity.endpoint import (
    TrinityEventBusEndpoint,
)
from trinity.extensibility.plugin import (
    BaseIsolatedPlugin,
)
from trinity.plugins.builtin.network_db.backends import (
    TrackingBackend,
)

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

    def on_ready(self, manager_eventbus: TrinityEventBusEndpoint) -> None:
        self.start()

    def _get_tracker(self) -> BaseConnectionTracker:
        backend = self.context.args.network_tracking_backend

        if backend is TrackingBackend.sqlite3:
            session = get_tracking_database(get_networkdb_path(self.context.trinity_config))
            return SQLiteConnectionTracker(session)
        elif backend is TrackingBackend.memory:
            return MemoryConnectionTracker()
        elif backend is TrackingBackend.disabled:
            return NoopConnectionTracker()
        else:
            raise Exception(f"INVARIANT: {backend}")

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
