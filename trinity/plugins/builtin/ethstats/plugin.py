import os
import asyncio
import platform

from argparse import (
    ArgumentParser,
    _SubParsersAction,
)

from trinity.constants import (
    MAINNET_NETWORK_ID,
    ROPSTEN_NETWORK_ID,
)
from trinity.endpoint import (
    TrinityEventBusEndpoint,
)
from trinity.extensibility import (
    BaseIsolatedPlugin,
)
from trinity._utils.shutdown import (
    exit_with_endpoint_and_services,
)

from trinity.plugins.builtin.ethstats.ethstats_service import (
    EthstatsService,
)

DEFAULT_SERVERS_URLS = {
    MAINNET_NETWORK_ID: 'wss://ethstats.net/api',
    ROPSTEN_NETWORK_ID: 'wss://ropsten-stats.parity.io/api',
}


class EthstatsPlugin(BaseIsolatedPlugin):
    server_url: str
    server_secret: str
    stats_interval: int
    node_id: str
    node_contact: str

    @property
    def name(self) -> str:
        return 'Ethstats'

    def get_default_server_url(self) -> str:
        return DEFAULT_SERVERS_URLS.get(self.boot_info.trinity_config.network_id, '')

    @classmethod
    def configure_parser(cls, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        ethstats_parser = arg_parser.add_argument_group('ethstats (experimental)')

        ethstats_parser.add_argument(
            '--ethstats',
            action='store_true',
            help='Enable node stats reporting service',
        )

        ethstats_parser.add_argument(
            '--ethstats-server-url',
            help='Node stats server URL (e. g. wss://example.com/api)',
            default=os.environ.get('ETHSTATS_SERVER_URL'),
        )
        ethstats_parser.add_argument(
            '--ethstats-server-secret',
            help='Node stats server secret',
            default=os.environ.get('ETHSTATS_SERVER_SECRET'),
        )
        ethstats_parser.add_argument(
            '--ethstats-node-id',
            help='Node ID for stats server',
            default=os.environ.get('ETHSTATS_NODE_ID', platform.node()),
        )
        ethstats_parser.add_argument(
            '--ethstats-node-contact',
            help='Node contact information for stats server',
            default=os.environ.get('ETHSTATS_NODE_CONTACT', ''),
        )
        ethstats_parser.add_argument(
            '--ethstats-interval',
            help='The interval at which data is reported back',
            default=10,
        )

    def on_ready(self, manager_eventbus: TrinityEventBusEndpoint) -> None:
        args = self.boot_info.args

        if not args.ethstats:
            return

        if not (args.ethstats_server_url or self.get_default_server_url()):
            self.logger.error(
                'You must provide ethstats server url using the `--ethstats-server-url`'
            )
            manager_eventbus.request_shutdown("Missing EthStats Server URL")
            return

        if not args.ethstats_server_secret:
            self.logger.error(
                'You must provide ethstats server secret using `--ethstats-server-secret`'
            )
            manager_eventbus.request_shutdown("Missing EthStats Server Secret")
            return

        if (args.ethstats_server_url):
            self.server_url = args.ethstats_server_url
        else:
            self.server_url = self.get_default_server_url()

        self.server_secret = args.ethstats_server_secret

        self.node_id = args.ethstats_node_id
        self.node_contact = args.ethstats_node_contact
        self.stats_interval = args.ethstats_interval

        self.start()

    def do_start(self) -> None:
        service = EthstatsService(
            self.boot_info,
            self.event_bus,
            self.server_url,
            self.server_secret,
            self.node_id,
            self.node_contact,
            self.stats_interval,
        )

        asyncio.ensure_future(exit_with_endpoint_and_services(self.event_bus, service))
        asyncio.ensure_future(service.run())
