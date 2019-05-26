import asyncio
from argparse import (
    Namespace,
    ArgumentParser,
    _SubParsersAction,
)
from typing import Iterable

from sqlalchemy.orm import Session

from eth_utils import to_tuple

from p2p.service import BaseService
from p2p.tracking.connection import (
    BaseConnectionTracker,
    NoopConnectionTracker,
)

from trinity._utils.shutdown import (
    exit_with_endpoint_and_services,
)
from trinity.config import (
    TrinityConfig,
)
from trinity.db.orm import get_tracking_database
from trinity.extensibility import (
    AsyncioIsolatedPlugin,
)
from trinity.db.network import (
    get_networkdb_path,
)
from trinity.endpoint import (
    TrinityEventBusEndpoint,
)
from trinity.exceptions import BadDatabaseError

from .connection.server import ConnectionTrackerServer
from .connection.tracker import (
    SQLiteConnectionTracker,
    MemoryConnectionTracker,
)
from .cli import (
    TrackingBackend,
    NormalizeTrackingBackend,
)
from .eth1_peer_db.server import PeerDBServer
from .eth1_peer_db.tracker import (
    BaseEth1PeerTracker,
    NoopEth1PeerTracker,
    SQLiteEth1PeerTracker,
    MemoryEth1PeerTracker,
)


class NetworkDBPlugin(AsyncioIsolatedPlugin):
    @property
    def name(self) -> str:
        return "Network Database"

    @property
    def normalized_name(self) -> str:
        return "network-db"

    @classmethod
    def configure_parser(cls,
                         arg_parser: ArgumentParser,
                         subparser: _SubParsersAction) -> None:
        tracking_parser = arg_parser.add_argument_group('network db')
        tracking_parser.add_argument(
            '--network-tracking-backend',
            help=(
                "Configure whether nodes are tracked and how. (sqlite3: persistent "
                "tracking across runs from an on-disk sqlite3 database, memory: tracking "
                "only in memory, do-not-track: no tracking)"
            ),
            action=NormalizeTrackingBackend,
            choices=('sqlite3', 'memory', 'do-not-track'),
            default=TrackingBackend.sqlite3,
            type=str,
        )
        tracking_parser.add_argument(
            '--disable-networkdb-plugin',
            help=(
                "Disables the builtin 'Networkt Database' plugin. "
                "**WARNING**: disabling this API without a proper replacement "
                "will cause your trinity node to crash."
            ),
            action='store_true',
        )
        tracking_parser.add_argument(
            '--disable-blacklistdb',
            help=(
                "Disables the blacklist database server component of the Network Database plugin."
                "**WARNING**: disabling this API without a proper replacement "
                "will cause your trinity node to crash."
            ),
            action='store_true',
        )
        tracking_parser.add_argument(
            '--disable-eth1-peer-db',
            help=(
                "Disables the ETH1.0 peer database server component of the Network Database plugin."
                "**WARNING**: disabling this API without a proper replacement "
                "will cause your trinity node to crash."
            ),
            action='store_true',
        )
        tracking_parser.add_argument(
            '--enable-experimental-eth1-peer-tracking',
            help=(
                "Enables the experimental tracking of metadata about successful "
                "connections to Eth1 peers."
            ),
            action='store_true',
        )

        # Command to wipe the on-disk database
        remove_db_parser = subparser.add_parser(
            'remove-network-db',
            help='Remove the on-disk sqlite database that tracks data about the p2p network',
        )
        remove_db_parser.set_defaults(func=cls.clear_node_db)

    def on_ready(self, manager_eventbus: TrinityEventBusEndpoint) -> None:
        if self.boot_info.args.disable_networkdb_plugin:
            self.logger.warning("Network Database disabled via CLI flag")
            # Allow this plugin to be disabled for extreme cases such as the
            # user swapping in an equivalent experimental version.
            return
        else:
            try:
                get_tracking_database(get_networkdb_path(self.boot_info.trinity_config))
            except BadDatabaseError as err:
                manager_eventbus.request_shutdown(
                    "Error loading network database.  Trying removing database "
                    f"with `remove-network-db` command:\n{err}"
                )
            else:
                self.start()

    @classmethod
    def clear_node_db(cls, args: Namespace, trinity_config: TrinityConfig) -> None:
        logger = cls.get_logger()
        db_path = get_networkdb_path(trinity_config)

        if db_path.exists():
            logger.info("Removing network database at: %s", db_path.resolve())
            db_path.unlink()
        else:
            logger.info("No network database found at: %s", db_path.resolve())

    _session: Session = None

    def _get_database_session(self) -> Session:
        if self._session is None:
            self._session = get_tracking_database(get_networkdb_path(self.boot_info.trinity_config))
        return self._session

    #
    # Blacklist Server
    #
    def _get_blacklist_tracker(self) -> BaseConnectionTracker:
        backend = self.boot_info.args.network_tracking_backend

        if backend is TrackingBackend.sqlite3:
            session = self._get_database_session()
            return SQLiteConnectionTracker(session)
        elif backend is TrackingBackend.memory:
            return MemoryConnectionTracker()
        elif backend is TrackingBackend.do_not_track:
            return NoopConnectionTracker()
        else:
            raise Exception(f"INVARIANT: {backend}")

    def _get_blacklist_service(self) -> ConnectionTrackerServer:
        tracker = self._get_blacklist_tracker()
        return ConnectionTrackerServer(
            event_bus=self.event_bus,
            tracker=tracker,
        )

    #
    # Eth1 Peer Server
    #
    def _get_eth1_tracker(self) -> BaseEth1PeerTracker:
        if not self.boot_info.args.enable_experimental_eth1_peer_tracking:
            return NoopEth1PeerTracker()

        backend = self.boot_info.args.network_tracking_backend

        if backend is TrackingBackend.sqlite3:
            session = self._get_database_session()

            # TODO: correctly determine protocols and versions
            protocols = ('eth',)
            protocol_versions = (63,)

            # TODO: get genesis_hash
            return SQLiteEth1PeerTracker(
                session,
                network_id=self.boot_info.trinity_config.network_id,
                protocols=protocols,
                protocol_versions=protocol_versions,
            )
        elif backend is TrackingBackend.memory:
            return MemoryEth1PeerTracker()
        elif backend is TrackingBackend.do_not_track:
            return NoopEth1PeerTracker()
        else:
            raise Exception(f"INVARIANT: {backend}")

    def _get_eth1_peer_server(self) -> PeerDBServer:
        tracker = self._get_eth1_tracker()

        return PeerDBServer(
            event_bus=self.event_bus,
            tracker=tracker,
        )

    @to_tuple
    def _get_services(self) -> Iterable[BaseService]:
        if self.boot_info.args.disable_blacklistdb:
            # Allow this plugin to be disabled for extreme cases such as the
            # user swapping in an equivalent experimental version.
            self.logger.warning("Blacklist Database disabled via CLI flag")
            return
        else:
            yield self._get_blacklist_service()

        if self.boot_info.args.disable_eth1_peer_db:
            # Allow this plugin to be disabled for extreme cases such as the
            # user swapping in an equivalent experimental version.
            self.logger.warning("ETH1 Peer Database disabled via CLI flag")
        else:
            yield self._get_eth1_peer_server()

    def do_start(self) -> None:
        try:
            tracker_services = self._get_services()
        except BadDatabaseError as err:
            self.logger.exception(f"Unrecoverable error in Network Plugin: {err}")
        else:
            asyncio.ensure_future(exit_with_endpoint_and_services(
                self.event_bus,
                *tracker_services
            ))
            for service in tracker_services:
                asyncio.ensure_future(service.run())
