from argparse import (
    Namespace,
    ArgumentParser,
    _SubParsersAction,
)
import logging

from trinity.config import (
    TrinityConfig,
)
from trinity.extensibility.plugin import (
    BaseMainProcessPlugin,
)
from trinity.db.network import (
    get_networkdb_path,
)

from .backends import TrackingBackend
from .cli import NormalizeTrackingBackend


class NetworkDBPlugin(BaseMainProcessPlugin):
    # we access this logger from a classmethod so it needs to be available on
    # the class (instead of as a computed property like the base class
    # prodived.
    logger = logging.getLogger(f'trinity.extensibility.plugin.BasePlugin#NetworkDBPlugin')

    @property
    def name(self) -> str:
        return "Network Database"

    @property
    def normalized_name(self) -> str:
        return "network-db"

    def configure_parser(self, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        tracking_parser = arg_parser.add_argument_group('network db')
        tracking_parser.add_argument(
            '--network-tracking-backend',
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
            'remove-network-db',
            help='Remove the on-disk sqlite database that tracks data about the p2p network',
        )
        attach_parser.set_defaults(func=self.clear_node_db)

    @classmethod
    def clear_node_db(cls, args: Namespace, trinity_config: TrinityConfig) -> None:
        db_path = get_networkdb_path(trinity_config)

        if db_path.exists():
            cls.logger.info("Removing network database at: %s", db_path.resolve())
            db_path.unlink()
        else:
            cls.logger.info("No network database found at: %s", db_path.resolve())
